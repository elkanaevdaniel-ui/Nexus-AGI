import asyncio
import logging
import os
import re
import shutil
import subprocess
import sys
import json
import urllib.request
import random
from datetime import datetime, time as dt_time
from pathlib import Path

# ── Directory constants ───────────────────────────────────────────────
BOT_DIR = Path(__file__).parent
NEXUS_DIR = BOT_DIR.parent / 'nexus-agi'

# ── Clean stale .pyc bytecode cache on every startup ──────────────────
# Prevents running old cached code when source files are updated
for _pycache in BOT_DIR.rglob("__pycache__"):
    try:
        shutil.rmtree(_pycache)
    except OSError:
        pass

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters, ConversationHandler
)

from config import (
    TELEGRAM_TOKEN, TELEGRAM_CHAT_ID,
    SCHEDULE_HOUR, SCHEDULE_MINUTE, WEEKLY_TOPICS
)
from database import (
    init_db, save_post, get_post, update_post, get_recent_topics,
    save_weekly_schedule, get_current_schedule, save_analytics
)
from scraper import fetch_news, pick_best_article
from ai_writer import generate_post, rewrite_post
from image_gen import generate_image, ALL_STYLES
from video_gen import generate_video, get_today_video_style, ALL_VIDEO_STYLES
from voice_handler import (
    ogg_to_wav, transcribe_audio, get_ai_response,
    text_to_speech, mp3_to_ogg, detect_bot_command, clear_history,
    get_jarvis_response, get_nexus_status, get_memory_stats
)

# ── Cloud Commands (remote control, budget, AI routing) ───────────────────────
from cloud_commands import (
    cmd_cloud_status, cmd_cloud_stats, cmd_cloud_logs,
    cmd_cloud_search, cmd_cloud_run, cmd_cloud_view,
    cmd_cloud_edit, cmd_cloud_budget, cmd_cloud_ai,
    cloud_callback_handler,
)

# ── CORTEX Orchestrator ────────────────────────────────────────────────
import sys as _sys
_sys.path.insert(0, str(NEXUS_DIR / 'divisions' / 'tier1-command' / 'cortex'))
try:
    from cortex import get_orchestrator as _get_cortex
except ImportError:
    _get_cortex = None
    logging.getLogger(__name__).warning("cortex module unavailable — some features disabled")

# ── ARGUS Monitor ──────────────────────────────────────────────────────────
_sys.path.insert(0, str(NEXUS_DIR / 'divisions' / 'tier5-operate' / 'argus'))
try:
    from argus import get_argus as _get_argus
except ImportError:
    _get_argus = None
    logging.getLogger(__name__).warning("argus module unavailable — some features disabled")

# ── Logging ────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler(str(BOT_DIR / "logs" / "bot.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ── Security ───────────────────────────────────────────────────────────
OWNER_FILTER = filters.Chat(chat_id=TELEGRAM_CHAT_ID)

# ── Conversation states ────────────────────────────────────────────────
WAITING_EDIT      = 1
WAITING_ANALYTICS = 2

# ── Module-level state ────────────────────────────────────────────────
current_post_id = None
_forced_style   = None   # set by /style, consumed once on next generate

# ── Daily style rotation (mirrors image_gen.py) ───────────────────────
DAILY_STYLES_MAP = {
    0: "photorealistic",  # Monday    - Realistic & Cinematic
    1: "anime",           # Tuesday   - Anime / Manga
    2: "cyberpunk",       # Wednesday - Cyberpunk / Neon
    3: "watercolor",      # Thursday  - Watercolor / Artistic
    4: "3d-cgi",          # Friday    - 3D CGI / Pixar
    5: "cinematic",       # Saturday  - Dramatic Cinematic
    6: "cartoon",         # Sunday    - Cartoon / Comic Book
}


def get_today_style() -> str:
    global _forced_style
    if _forced_style:
        s = _forced_style
        _forced_style = None
        return s
    return DAILY_STYLES_MAP.get(datetime.now().weekday(), "photorealistic")


def should_use_video() -> bool:
    """
    60% image / 40% video split.
    Video days: Wed(2), Fri(4), Sun(6) = 3/7 days guaranteed.
    Other days use daily-seeded random for ~10% extra.
    """
    import random as _rnd
    today = datetime.now()
    if today.weekday() in (2, 4, 6):
        return True
    day_seed = int(today.strftime("%Y%m%d"))
    rng = _rnd.Random(day_seed)
    return rng.random() < 0.1


def get_current_topic() -> tuple:
    """Return (topic_str, topic_index) from DB override or week-based auto."""
    schedule = get_current_schedule()
    if schedule:
        idx = schedule.get("topic_index", 0)
    else:
        idx = datetime.now().isocalendar()[1] % len(WEEKLY_TOPICS)
    return WEEKLY_TOPICS[idx], idx


# ── Keyboards ─────────────────────────────────────────────────────────

def get_main_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [["📰 Generate Post", "📋 Schedule"],
         ["📊 Analytics",     "🎲 Random Style"],
         ["❓ Help"]],
        resize_keyboard=True
    )


def get_post_keyboard(post_id, article_url=None) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton("✅ Approve",      callback_data=f"approve_{post_id}"),
         InlineKeyboardButton("🔄 New Topic",   callback_data=f"newtopic_{post_id}")],
        [InlineKeyboardButton("🎨 New Image",   callback_data=f"newimage_{post_id}"),
         InlineKeyboardButton("✏️ Edit Text",   callback_data=f"edittext_{post_id}")],
        [InlineKeyboardButton("📊 Stats",     callback_data=f"stats_{post_id}")],
    ]
    if article_url:
        buttons.append([InlineKeyboardButton("🔗 Read Article", url=article_url)])
    return InlineKeyboardMarkup(buttons)


# ── Core send helper ──────────────────────────────────────────────────

async def send_post_to_user(context: ContextTypes.DEFAULT_TYPE, post_id: int):
    """Send post photo+text as a single visual unit.

    If the full caption fits within Telegram's 1024-char photo caption
    limit, it is sent as a photo caption.  Otherwise the photo is sent
    first and the full post text follows as a reply to the photo message
    so they stay linked in the chat.
    """
    post = get_post(post_id)
    if not post:
        return

    article_title = post.get('article_title', 'N/A')
    article_url = post.get('article_url', '')
    source_link = (f"[{article_title}]({article_url})"
                   if article_url else article_title)
    header = (
        f"📰 *Today's LinkedIn Post*\n\n"
        f"📌 *Topic:* {post.get('topic', 'N/A')}\n"
        f"🔗 *Source:* {source_link}\n\n"
        f"---\n\n"
    )
    footer = f"\n\n---\n_Post ID: #{post_id}_"
    full_text = header + post['post_text'] + footer

    keyboard = get_post_keyboard(post_id, article_url=post.get("article_url"))
    img_path = post.get("image_path")

    from telegram.constants import ParseMode

    if img_path and os.path.exists(img_path):
        if len(full_text) <= 1024:
            # Short enough — send image + text as one message
            with open(img_path, "rb") as img:
                await context.bot.send_photo(
                    chat_id=TELEGRAM_CHAT_ID,
                    photo=img,
                    caption=full_text,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
        else:
            # Text too long for caption — send photo first, then reply
            # with full text so they stay linked in the conversation
            short_caption = (
                f"📰 *{post.get('topic', 'LinkedIn Post')}*\n"
                f"_Full post below ↓_"
            )
            with open(img_path, "rb") as img:
                sent_photo = await context.bot.send_photo(
                    chat_id=TELEGRAM_CHAT_ID,
                    photo=img,
                    caption=short_caption,
                    parse_mode="Markdown",
                )
            # Disable link preview so article OG image doesn't override our image
            await context.bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=full_text[:4096],
                parse_mode="Markdown",
                reply_markup=keyboard,
                reply_to_message_id=sent_photo.message_id,
                disable_web_page_preview=True,
            )
    else:
        await context.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=full_text[:4096],
            parse_mode="Markdown",
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )


async def send_video_to_user(
    context: ContextTypes.DEFAULT_TYPE,
    post_id: int,
    video_path: str,
) -> None:
    """Send an animated video post to the owner with inline keyboard.

    If the full caption exceeds Telegram's 1024-char video caption limit,
    the video is sent with a short caption and the full post follows as a
    reply message so nothing gets silently truncated.
    """
    post = get_post(post_id)
    if not post:
        return

    video_style = get_today_video_style()
    article_title = post.get('article_title', 'N/A')
    article_url = post.get('article_url', '')
    source_link = (f"[{article_title}]({article_url})"
                   if article_url else article_title)

    header = (
        "🎬 *Today LinkedIn Post — Video*\n\n"
        f"📌 *Topic:* {post.get('topic', 'N/A')}\n"
        f"🎞 Video Style: {video_style}\n"
        f"🔗 *Source:* {source_link}\n\n"
        "---\n\n"
    )
    footer = f"\n\n---\n_Post ID: #{post_id}_"
    full_text = header + post['post_text'] + footer
    keyboard = get_post_keyboard(post_id, article_url=article_url)

    try:
        if len(full_text) <= 1024:
            with open(video_path, "rb") as vid:
                await context.bot.send_video(
                    chat_id=TELEGRAM_CHAT_ID,
                    video=vid,
                    caption=full_text,
                    parse_mode="Markdown",
                    reply_markup=keyboard,
                    width=1200,
                    height=628,
                    supports_streaming=True,
                )
        else:
            short_caption = (
                f"🎬 *{post.get('topic', 'LinkedIn Post')}*\n"
                f"🎞 _{video_style}_ — _Full post below ↓_"
            )
            with open(video_path, "rb") as vid:
                sent_video = await context.bot.send_video(
                    chat_id=TELEGRAM_CHAT_ID,
                    video=vid,
                    caption=short_caption,
                    parse_mode="Markdown",
                    width=1200,
                    height=628,
                    supports_streaming=True,
                )
            await context.bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=full_text[:4096],
                parse_mode="Markdown",
                reply_markup=keyboard,
                reply_to_message_id=sent_video.message_id,
            )
        logger.info("Video sent to Telegram: %s", video_path)
    except Exception as exc:
        logger.error("Failed to send video, falling back to image: %s", exc)
        await send_post_to_user(context, post_id)


# ── Post Generation ───────────────────────────────────────────────────

async def generate_and_send_post(context: ContextTypes.DEFAULT_TYPE, article: dict = None):
    """Generate a new LinkedIn post from article (or fetch one) and send for approval."""
    global current_post_id

    await context.bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text="🔍 Fetching today's AI & Cybersecurity news..."
    )

    if article is None:
        articles = fetch_news()
        used_topics = get_recent_topics(5)
        article = pick_best_article(articles, used_topics)

    if not article:
        await context.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text="❌ No suitable articles found. Try /post again later."
        )
        return

    await context.bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=(
            f"✅ Found: *{article['title']}*\n"
            f"Source: _{article.get('source', 'unknown')}_"
        ),
        parse_mode="Markdown"
    )

    # ── Generate post text ───────────────────────────────────────────────
    await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="✍️ Writing LinkedIn post...")
    result    = generate_post(article)  # returns {post_text, image_prompt, metadata}
    post_text = result["post_text"]

    # ── Content quality check ────────────────────────────────────────
    post_words = len(re.sub(r"#\w+", "", post_text).split())
    content_is_valid = (
        "POST GENERATION FAILED" not in post_text
        and post_words >= 50
    )

    # Warn user if LLM failed and we got a placeholder
    if not content_is_valid:
        await context.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=(
                "⚠️ *LLM call failed* — post text is a placeholder.\n"
                "Use 🔄 New Topic to retry or ✏️ Edit Text to write manually.\n"
                "Check API keys (OpenRouter / Gemini) if this keeps happening."
            ),
            parse_mode="Markdown",
        )

    # Save post to DB first to get post_id
    post_id = save_post(
        topic=article["title"][:100],
        article_title=article["title"],
        article_url=article.get("url", ""),
        post_text=post_text,
        image_url="",
        image_path=""
    )
    current_post_id = post_id

    # ── Generate image ONLY if content is valid ───────────────────────
    img_path = None
    if content_is_valid:
        await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="🎨 Generating image...")
        style    = get_today_style()
        img_path = generate_image(
            title=article["title"],
            content=article.get("content") or article.get("summary") or "",
            post_id=post_id,
            url=article.get("url", ""),
            force_style=style,
            post_text=post_text,
        )  # returns str path, NOT a tuple

        if img_path:
            update_post(post_id, image_path=img_path, image_url="")
    else:
        logger.warning(
            "Skipping image+video — content invalid (%d words, need 50+)", post_words
        )

    # ── 60% image / 40% video decision ────────────────────────────────
    # Only generate video if content is valid AND we have an image
    use_video = should_use_video() if content_is_valid else False

    if use_video and img_path:
        await context.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=f"🎬 Generating video ({get_today_video_style()} style)...⏳ ~30s"
        )
        try:
            video_path = generate_video(
                image_path=img_path,
                post_id=post_id,
                duration=25,
            )
            if video_path:
                update_post(post_id, image_url=f"video:{video_path}")
                await send_video_to_user(context, post_id, video_path)
                return
            else:
                logger.warning("Video generation failed, falling back to image")
        except Exception as vid_exc:
            logger.error("Video generation error: %s", vid_exc)

    await send_post_to_user(context, post_id)


# ── Scheduled Jobs ────────────────────────────────────────────────────

async def job_daily_post(context: ContextTypes.DEFAULT_TYPE):
    try:
        await generate_and_send_post(context)
    except Exception as exc:
        logger.error("Daily post job failed: %s", exc)
        await context.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=f"❌ Daily post failed: {exc}"
        )


async def job_weekly_topic_suggestion(context: ContextTypes.DEFAULT_TYPE):
    """Sunday 8PM: suggest next week topic."""
    topic_buttons = [
        [InlineKeyboardButton(f"{i}: {t}", callback_data=f"settopic_{i}")]
        for i, t in enumerate(WEEKLY_TOPICS)
    ]
    await context.bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=(
            "📅 *Weekly Topic Selection*\n\n"
            "Choose next week's content theme:"
        ),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(topic_buttons)
    )


# ── Command Handlers ──────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic_str, idx = get_current_topic()
    style = DAILY_STYLES_MAP.get(datetime.now().weekday(), "photorealistic")
    await update.message.reply_text(
        f"🤖 *LinkedIn AI Bot Active!*\n\n"
        f"📌 *This week's topic:* {topic_str}\n"
        f"🎨 *Today's style:* {style}\n\n"
        "*Content:*\n"
        "/post - Generate a new post now\n"
        "/last - Show last generated post\n"
        "/search [keyword] - Search & generate\n"
        "/schedule - View weekly schedule\n"
        "/topic [0-9] - Switch topic\n"
        "/style [name] - Force image style\n"
        "/video [style] - Generate video\n\n"
        "*Cloud Control:*\n"
        "/status - System health & services\n"
        "/stats - Post & API statistics\n"
        "/logs [n] - View recent logs\n"
        "/budget - API cost tracking\n"
        "/ai [question] - Smart AI query\n"
        "/run [cmd] - Remote shell command\n"
        "/view [file] - View file\n"
        "/edit [file] - Edit file",
        parse_mode="Markdown",
        reply_markup=get_main_reply_keyboard()
    )


async def cmd_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 Starting post generation...")
    await generate_and_send_post(context)


async def cmd_last(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_post_id
    if current_post_id:
        await send_post_to_user(context, current_post_id)
    else:
        await update.message.reply_text(
            "No posts generated yet. Use /post or tap 📰 Generate Post!"
        )


async def cmd_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic_str, idx = get_current_topic()
    style = DAILY_STYLES_MAP.get(datetime.now().weekday(), "photorealistic")
    lines_out = [
        "📅 *Weekly Schedule*\n",
        f"📌 *Current Topic:* {topic_str} (#{idx})",
        f"🎨 *Today's Style:* {style}",
        f"⏰ *Daily Post:* {SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d} UTC\n",
        "*Art Style Rotation:*",
    ]
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for i, (d, s) in enumerate(zip(days, DAILY_STYLES_MAP.values())):
        marker = "▶️" if i == datetime.now().weekday() else "  "
        lines_out.append(f"{marker} *{d}:* {s}")
    lines_out.append("\n*Available Topics:*")
    for i, t in enumerate(WEEKLY_TOPICS):
        marker = "✅" if i == idx else "•"
        lines_out.append(f"{marker} {i}: {t}")

    topic_buttons = [
        [InlineKeyboardButton(f"Switch to: {t[:30]}", callback_data=f"settopic_{i}")]
        for i, t in enumerate(WEEKLY_TOPICS)
    ]
    await update.message.reply_text(
        "\n".join(lines_out),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(topic_buttons)
    )


async def cmd_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Switch weekly topic: /topic 3 or show picker."""
    if context.args:
        try:
            idx = int(context.args[0])
            if 0 <= idx < len(WEEKLY_TOPICS):
                week_start = datetime.now().strftime("%Y-W%W")
                save_weekly_schedule(week_start, WEEKLY_TOPICS[idx], idx)
                await update.message.reply_text(
                    f"✅ Topic switched to: *{WEEKLY_TOPICS[idx]}*",
                    parse_mode="Markdown"
                )
                return
            await update.message.reply_text(f"❌ Index must be 0-{len(WEEKLY_TOPICS)-1}")
            return
        except ValueError:
            pass
    topic_buttons = [
        [InlineKeyboardButton(f"{i}: {t}", callback_data=f"settopic_{i}")]
        for i, t in enumerate(WEEKLY_TOPICS)
    ]
    await update.message.reply_text(
        "📌 *Select Weekly Topic:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(topic_buttons)
    )


async def cmd_style(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Force style for next post: /style anime or show picker."""
    global _forced_style
    if context.args:
        style_arg = context.args[0].lower()
        if style_arg in ALL_STYLES:
            _forced_style = style_arg
            await update.message.reply_text(
                f"🎨 Style locked to *{style_arg}* for next post!",
                parse_mode="Markdown"
            )
            return
        await update.message.reply_text(
            f"❌ Unknown style. Available: {', '.join(ALL_STYLES)}"
        )
        return
    style_buttons = [
        [InlineKeyboardButton(s, callback_data=f"setstyle_{s}")]
        for s in ALL_STYLES
    ]
    await update.message.reply_text(
        "🎨 *Choose Image Style for Next Post:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(style_buttons)
    )


async def cmd_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate a video from the last post image: /video [style]"""
    global current_post_id
    if not current_post_id:
        await update.message.reply_text(
            "❌ No post generated yet. Use /post first."
        )
        return

    post = get_post(current_post_id)
    if not post or not post.get("image_path") or not os.path.exists(post["image_path"]):
        await update.message.reply_text(
            "❌ No image found for last post. Run /post first."
        )
        return

    force_style = None
    if context.args:
        arg = context.args[0].lower()
        if arg in ALL_VIDEO_STYLES:
            force_style = arg
        elif arg == "random":
            force_style = "random"
        else:
            styles_str = ', '.join(ALL_VIDEO_STYLES)
            await update.message.reply_text(
                f"❌ Unknown style. Available: {styles_str}"
            )
            return

    style_name = force_style or get_today_video_style()
    await update.message.reply_text(
        (f"🎬 Generating video ({style_name} style) from last post...\n"
        "⏳ This takes ~30 seconds...")
    )
    try:
        video_path = generate_video(
            image_path=post["image_path"],
            post_id=current_post_id,
            duration=25,
            force_style=force_style,
        )
        if video_path:
            await send_video_to_user(context, current_post_id, video_path)
        else:
            await update.message.reply_text("❌ Video generation failed. Check logs.")
    except Exception as exc:
        logger.error("cmd_video error: %s", exc)
        await update.message.reply_text(f"❌ Error: {exc}")



async def cmd_jarvis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /jarvis <message> — JARVIS responds with voice note."""
    import tempfile, os
    chat_id = update.effective_chat.id
    args = context.args
    if not args:
        await update.message.reply_text(
            "🤖 *JARVIS v0.1 online, sir.*\n"
            "Usage: `/jarvis <your message>`\n"
            "Example: `/jarvis status report`\n\n"
            "Or say *hey jarvis* in any text message.",
            parse_mode="Markdown"
        )
        return

    user_text = " ".join(args)
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    # Get JARVIS personality response
    jarvis_reply = await get_jarvis_response(chat_id, user_text, mode="voice")

    # Check for bot command tokens
    bot_cmd = detect_bot_command(jarvis_reply)
    clean_reply = jarvis_reply
    for token in ["POST_NOW", "SHOW_LAST", "SHOW_SCHEDULE", "SHOW_ANALYTICS", "SHOW_HELP"]:
        clean_reply = clean_reply.replace(token, "").strip()

    # Send text reply with JARVIS branding
    await update.message.reply_text(f"🤖 *JARVIS:* {clean_reply}", parse_mode="Markdown")

    # Generate and send British accent voice note
    with tempfile.TemporaryDirectory() as tmpdir:
        mp3_path = os.path.join(tmpdir, "jarvis_reply.mp3")
        ogg_path = os.path.join(tmpdir, "jarvis_reply.ogg")
        await context.bot.send_chat_action(chat_id=chat_id, action="record_voice")
        if await text_to_speech(clean_reply or "Very well, sir.", mp3_path):
            if await mp3_to_ogg(mp3_path, ogg_path):
                with open(ogg_path, "rb") as audio:
                    await context.bot.send_voice(
                        chat_id=chat_id, voice=audio,
                        caption="🇬🇧 JARVIS v0.1"
                    )

    # Execute any detected bot command
    if bot_cmd == "POST_NOW":
        await update.message.reply_text("🚀 JARVIS initiating post generation...")
        await cmd_post(update, context)
    elif bot_cmd == "SHOW_LAST":
        await cmd_last(update, context)
    elif bot_cmd == "SHOW_SCHEDULE":
        await cmd_schedule(update, context)
    elif bot_cmd == "SHOW_HELP":
        await cmd_start(update, context)


async def cmd_nexus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /nexus — JARVIS reads NEXUS docs and gives a voice status report."""
    import tempfile, os
    chat_id = update.effective_chat.id

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    await update.message.reply_text(
        "📊 *Accessing NEXUS Intelligence Network...*",
        parse_mode="Markdown"
    )

    # Generate NEXUS status report via JARVIS
    status_report = await get_nexus_status(chat_id)
    clean_report = status_report
    for token in ["POST_NOW", "SHOW_LAST", "SHOW_SCHEDULE", "SHOW_ANALYTICS", "SHOW_HELP"]:
        clean_report = clean_report.replace(token, "").strip()

    # Send text report
    await update.message.reply_text(
        f"🤖 *JARVIS NEXUS Report:*\n\n{clean_report}",
        parse_mode="Markdown"
    )

    # Send as voice note
    with tempfile.TemporaryDirectory() as tmpdir:
        mp3_path = os.path.join(tmpdir, "nexus_report.mp3")
        ogg_path = os.path.join(tmpdir, "nexus_report.ogg")
        await context.bot.send_chat_action(chat_id=chat_id, action="record_voice")
        if await text_to_speech(clean_report, mp3_path):
            if await mp3_to_ogg(mp3_path, ogg_path):
                with open(ogg_path, "rb") as audio:
                    await context.bot.send_voice(
                        chat_id=chat_id, voice=audio,
                        caption="📊 NEXUS Status Report — JARVIS"
                    )

    # Show memory stats
    stats = get_memory_stats()
    await update.message.reply_text(
        f"🧠 *JARVIS Memory:* {stats['total_turns']} conversation turns logged.",
        parse_mode="Markdown"
    )


async def cmd_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prompt user to paste LinkedIn post analytics."""
    await update.message.reply_text(
        "📊 *Log LinkedIn Analytics*\n\n"
        "Paste your post stats in this format:\n"
        "`post_id views likes comments shares ctr`\n\n"
        "Example:\n"
        "`42 1250 87 23 15 3.2`\n\n"
        "Or paste any free-form analytics text and I will parse it.",
        parse_mode="Markdown"
    )
    return WAITING_ANALYTICS


async def handle_analytics_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Parse analytics text, save to DB, give AI advice."""
    text = update.message.text.strip()
    parts = text.split()
    post_id, views, likes, comments, shares, ctr = 0, 0, 0, 0, 0, 0.0
    try:
        if len(parts) >= 6 and all(p.replace(".", "").isdigit() for p in parts[:6]):
            post_id  = int(parts[0])
            views    = int(parts[1])
            likes    = int(parts[2])
            comments = int(parts[3])
            shares   = int(parts[4])
            ctr      = float(parts[5])
        else:
            import re
            nums = re.findall(r"\d+\.?\d*", text)
            if len(nums) >= 2:
                views = int(float(nums[0]))
                likes = int(float(nums[1])) if len(nums) > 1 else 0
                comments = int(float(nums[2])) if len(nums) > 2 else 0
                shares   = int(float(nums[3])) if len(nums) > 3 else 0
                ctr      = float(nums[4]) if len(nums) > 4 else 0.0
    except (ValueError, IndexError):
        pass

    save_analytics(post_id, views, likes, comments, shares, ctr, notes=text[:500])
    engagement = round((likes + comments + shares) / max(views, 1) * 100, 2)

    advice = ""
    if engagement > 5:
        advice = "🔥 Excellent engagement! Double down on this topic style."
    elif engagement > 2:
        advice = "👍 Good engagement. Try a stronger hook next time."
    else:
        advice = "💡 Low engagement. Try: stronger opener, more controversy, or a story format."

    await update.message.reply_text(
        f"✅ *Analytics Saved!*\n\n"
        f"Views: {views} | Likes: {likes} | Comments: {comments}\n"
        f"Shares: {shares} | CTR: {ctr}%\n"
        f"Engagement Rate: *{engagement}%*\n\n"
        f"{advice}",
        parse_mode="Markdown"
    )
    return ConversationHandler.END


# ── Text message router (reply keyboard) ──────────────────────────────

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import tempfile, os
    text = update.message.text
    chat_id = update.effective_chat.id

    # JARVIS activation: "hey jarvis" or "jarvis," prefix
    tl = text.lower().strip()
    if tl.startswith("hey jarvis") or tl.startswith("jarvis,") or tl.startswith("jarvis "):
        # Strip the activation prefix
        for prefix in ("hey jarvis", "jarvis,", "jarvis"):
            if tl.startswith(prefix):
                user_msg = text[len(prefix):].strip() or "hello"
                break
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        jarvis_reply = await get_jarvis_response(chat_id, user_msg, mode="voice")
        bot_cmd = detect_bot_command(jarvis_reply)
        clean_reply = jarvis_reply
        for token in ["POST_NOW", "SHOW_LAST", "SHOW_SCHEDULE", "SHOW_ANALYTICS", "SHOW_HELP"]:
            clean_reply = clean_reply.replace(token, "").strip()
        await update.message.reply_text(
            f"🤖 *JARVIS:* {clean_reply}", parse_mode="Markdown"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            mp3_path = os.path.join(tmpdir, "j.mp3")
            ogg_path = os.path.join(tmpdir, "j.ogg")
            await context.bot.send_chat_action(chat_id=chat_id, action="record_voice")
            if await text_to_speech(clean_reply or "Very well.", mp3_path):
                if await mp3_to_ogg(mp3_path, ogg_path):
                    with open(ogg_path, "rb") as audio:
                        await context.bot.send_voice(
                            chat_id=chat_id, voice=audio,
                            caption="🇬🇧 JARVIS"
                        )
        if bot_cmd == "POST_NOW":
            await cmd_post(update, context)
        elif bot_cmd == "SHOW_LAST":
            await cmd_last(update, context)
        elif bot_cmd == "SHOW_SCHEDULE":
            await cmd_schedule(update, context)
        elif bot_cmd == "SHOW_HELP":
            await cmd_start(update, context)
        return

    if text == "📰 Generate Post":
        await cmd_post(update, context)
    elif text == "📋 Schedule":
        await cmd_schedule(update, context)
    elif text == "📊 Analytics":
        await cmd_analytics(update, context)
    elif text == "🎲 Random Style":
        global _forced_style
        _forced_style = random.choice(ALL_STYLES)
        await update.message.reply_text(
            f"🎲 Style randomised to *{_forced_style}* for next post!",
            parse_mode="Markdown"
        )
    elif text == "❓ Help":
        await cmd_start(update, context)


# ── Inline Callback Handler ────────────────────────────────────────────

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_post_id
    query = update.callback_query
    if query.from_user.id != TELEGRAM_CHAT_ID:
        await query.answer("Unauthorized.", show_alert=False)
        return
    await query.answer()

    data = query.data

    # ── settopic callback ──────────────────────────────────────────────
    if data.startswith("settopic_"):
        try:
            idx = int(data.split("_", 1)[1])
            if 0 <= idx < len(WEEKLY_TOPICS):
                week_start = datetime.now().strftime("%Y-W%W")
                save_weekly_schedule(week_start, WEEKLY_TOPICS[idx], idx)
                await query.edit_message_text(
                    f"✅ *Topic set to:* {WEEKLY_TOPICS[idx]}",
                    parse_mode="Markdown"
                )
        except (ValueError, IndexError):
            await query.answer("Invalid topic index")
        return

    # ── setstyle callback ──────────────────────────────────────────────
    if data.startswith("setstyle_"):
        global _forced_style
        style = data.split("_", 1)[1]
        if style in ALL_STYLES:
            _forced_style = style
            await query.edit_message_text(
                f"🎨 *Style locked to {style}* for next post!",
                parse_mode="Markdown"
            )
        return

    # ── post action callbacks ──────────────────────────────────────────
    try:
        action, post_id_str = data.rsplit("_", 1)
        post_id = int(post_id_str)
    except (ValueError, AttributeError):
        await query.answer("Unknown action")
        return

    post = get_post(post_id)
    if not post:
        await query.edit_message_text("❌ Post not found.")
        return

    if action == "approve":
        update_post(post_id, status="approved", approved_at=datetime.now().isoformat())
        final_text = (
            f"✅ *Post #{post_id} Approved!*\n\n"
            f"*Your LinkedIn post:*\n\n"
            f"```\n{post['post_text']}\n```\n\n"
            f"📋 Copy and post on LinkedIn!"
        )
        try:
            await query.edit_message_caption(caption="✅ Post approved!", reply_markup=None)
        except Exception:
            pass
        await query.message.reply_text(final_text, parse_mode="Markdown")
        if post.get("image_path") and os.path.exists(post["image_path"]):
            await query.message.reply_text(
                f"🖼️ Image saved at:\n`{post['image_path']}`",
                parse_mode="Markdown"
            )

    elif action == "newtopic":
        try:
            await query.edit_message_caption(caption="🔄 Fetching a new topic...", reply_markup=None)
        except Exception:
            pass
        await generate_and_send_post(context)

    elif action == "newimage":
        try:
            await query.edit_message_caption(caption="🎨 Generating a new image...", reply_markup=None)
        except Exception:
            pass
        # BUG FIX: correct generate_image signature, returns str not tuple
        img_path = generate_image(
            title=post["topic"],
            content=post["post_text"][:500],
            post_id=post_id,
            url=post.get("article_url", ""),
            force_style="random"
        )
        if img_path:
            update_post(post_id, image_path=img_path)
            await query.message.reply_text("✅ New image generated!")
            await send_post_to_user(context, post_id)
        else:
            await query.message.reply_text("❌ Image generation failed. Try again.")

    elif action == "edittext":
        context.user_data["editing_post_id"] = post_id
        await query.message.reply_text(
            "✏️ Send me your edit instruction:\n"
            "Examples:\n"
            "- 'Make it shorter'\n"
            "- 'More focus on cybersecurity'\n"
            "- 'Add more emojis'\n"
            "- 'Change tone to be more casual'"
        )
        return WAITING_EDIT

    elif action == "stats":
        await query.message.reply_text(
            f"📊 *Post #{post_id} Stats*\n\n"
            f"Topic: {post['topic']}\n"
            f"Status: {post['status']}\n"
            f"Created: {post['created_at']}\n"
            f"Source: {post.get('article_url', 'N/A')}",
            parse_mode="Markdown"
        )


# ── Edit text conversation handler ────────────────────────────────────

async def handle_edit_instruction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    post_id = context.user_data.get("editing_post_id")
    if not post_id:
        return ConversationHandler.END
    instruction = update.message.text
    post = get_post(post_id)
    if not post:
        return ConversationHandler.END
    await update.message.reply_text("✍️ Rewriting post...")
    new_text = rewrite_post(post["post_text"], instruction)
    update_post(post_id, post_text=new_text)
    await update.message.reply_text(
        f"✅ *Updated Post:*\n\n{new_text}",
        parse_mode="Markdown",
        reply_markup=get_post_keyboard(post_id)
    )
    return ConversationHandler.END


# ── Security: silent catch-all ─────────────────────────────────────────




async def cmd_argus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ARGUS v0.1 — System monitor: /argus | costs | status | budget"""
    chat_id = update.effective_chat.id
    args    = context.args or []
    arg_str = " ".join(args).strip().lower()
    if _get_argus is None:
        await update.message.reply_text("⚠️ ARGUS module not available (missing dependency).")
        return
    argus   = _get_argus()
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    if arg_str == "costs":
        text = argus.format_costs()
    elif arg_str == "status":
        text = argus.format_status()
    elif arg_str == "budget":
        text = argus.format_budget()
    else:
        text = argus.format_full_report()
    await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_cortex(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """CORTEX v0.1 — Goal orchestration: /cortex [goal] | status | list | nexus-XXX"""
    chat_id = update.effective_chat.id
    args    = context.args or []
    arg_str = " ".join(args).strip()

    if _get_cortex is None:
        await update.message.reply_text("⚠️ CORTEX module not available (missing dependency).")
        return
    cortex = _get_cortex()

    # ── /cortex (no args) — help ──────────────────────────────────────────
    if not arg_str:
        await update.message.reply_text(
            "🔷 *CORTEX v0.1 — NEXUS Orchestrator*\n\n"
            "Submit a goal and CORTEX will decompose it into subtasks,\n"
            "route each to the correct NEXUS division, and track progress.\n\n"
            "*Usage:*\n"
            "`/cortex [goal]` — Submit a new goal\n"
            "`/cortex status` — Show active tasks\n"
            "`/cortex list`   — Recent task history\n"
            "`/cortex nexus-001` — Task detail\n\n"
            "*Example:*\n"
            "`/cortex Build a crypto price alert system`\n"
            "`/cortex Research top 5 AI startups this week`",
            parse_mode="Markdown"
        )
        return

    # ── /cortex status ────────────────────────────────────────────────────
    if arg_str.lower() == "status":
        await update.message.reply_text(
            cortex.format_status(), parse_mode="Markdown"
        )
        return

    # ── /cortex list ──────────────────────────────────────────────────────
    if arg_str.lower() == "list":
        await update.message.reply_text(
            cortex.format_list(limit=5), parse_mode="Markdown"
        )
        return

    # ── /cortex nexus-XXX — task detail ───────────────────────────────────
    if arg_str.lower().startswith("nexus-"):
        await update.message.reply_text(
            cortex.format_task_detail(arg_str.lower()), parse_mode="Markdown"
        )
        return

    # ── /cortex [goal] — process new goal ────────────────────────────────
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    await update.message.reply_text(
        f"🔷 *CORTEX PROCESSING*\n\n"
        f"📋 *Goal:* {arg_str[:200]}\n\n"
        "🧠 _Decomposing into subtasks..._",
        parse_mode="Markdown"
    )

    try:
        result = await cortex.process_goal(arg_str)
        await update.message.reply_text(
            result["telegram"], parse_mode="Markdown"
        )
    except Exception as exc:
        logger.error("CORTEX cmd error: %s", exc)
        await update.message.reply_text(
            f"❌ *CORTEX Error:* `{str(exc)[:200]}`\n\n"
            "_Please try again, sir._",
            parse_mode="Markdown"
        )

async def cmd_restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Restart the bot"""
    await update.message.reply_text(
        "🔄 *Restarting NEXUS Bot...* \nStand by, sir. I'll be back online in a moment.",
        parse_mode="Markdown"
    )
    # Delay to let message send
    import asyncio
    await asyncio.sleep(1)
    # Restart via launch_all.sh
    subprocess.Popen(
        ['bash', str(BOT_DIR / 'launch_all.sh')],
        stdout=open(str(BOT_DIR / 'logs' / 'restart.log'), 'w'),
        stderr=subprocess.STDOUT,
        start_new_session=True
    )
    # Exit current process - watchdog or launch_all will restart
    sys.exit(0)

async def unauthorized_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    msg  = update.effective_message
    logger.warning(
        "UNAUTHORIZED: user_id=%s username=%s chat_id=%s text=%r",
        user.id if user else "?",
        user.username if user else "?",
        chat.id if chat else "?",
        msg.text if msg else ""
    )
    # Silent ignore


# ── Main ──────────────────────────────────────────────────────────────



async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming voice messages — STT → AI → TTS pipeline."""
    import tempfile, os
    chat_id = update.effective_chat.id
    msg = update.message

    # Show typing indicator
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    # Download OGG voice file from Telegram
    voice = msg.voice
    voice_file = await voice.get_file()

    with tempfile.TemporaryDirectory() as tmpdir:
        ogg_path = os.path.join(tmpdir, "voice.ogg")
        wav_path = os.path.join(tmpdir, "voice.wav")
        mp3_path = os.path.join(tmpdir, "reply.mp3")
        ogg_reply_path = os.path.join(tmpdir, "reply.ogg")

        # Download voice
        await voice_file.download_to_drive(ogg_path)

        # Convert OGG → WAV
        if not await ogg_to_wav(ogg_path, wav_path):
            await msg.reply_text("❌ Could not process your voice message. Please try again.")
            return

        # Transcribe speech → text
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        user_text = await transcribe_audio(wav_path)

        if not user_text:
            await msg.reply_text("🎙️ I couldn't understand that. Please speak clearly and try again.")
            return

        # Show what was heard
        await msg.reply_text(f"🎙️ *I heard:* {user_text}", parse_mode="Markdown")

        # Get AI response
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        ai_reply = await get_ai_response(chat_id, user_text)

        # Check if AI wants to trigger a bot command
        bot_cmd = detect_bot_command(ai_reply)
        clean_reply = ai_reply.replace("POST_NOW", "").replace("SHOW_LAST", "").replace(
            "SHOW_SCHEDULE", "").replace("SHOW_ANALYTICS", "").replace("SHOW_HELP", "").strip()

        # Send text reply
        if clean_reply:
            await msg.reply_text(f"🤖 {clean_reply}")

        # Convert reply to voice
        await context.bot.send_chat_action(chat_id=chat_id, action="record_voice")
        if await text_to_speech(clean_reply or "Done!", mp3_path):
            if await mp3_to_ogg(mp3_path, ogg_reply_path):
                with open(ogg_reply_path, "rb") as audio:
                    await context.bot.send_voice(chat_id=chat_id, voice=audio)

        # Execute bot command if detected
        if bot_cmd == "POST_NOW":
            await msg.reply_text("🚀 Starting post generation...")
            await cmd_post(update, context)
        elif bot_cmd == "SHOW_LAST":
            await cmd_last(update, context)
        elif bot_cmd == "SHOW_SCHEDULE":
            await cmd_schedule(update, context)
        elif bot_cmd == "SHOW_HELP":
            await cmd_start(update, context)


async def post_init(application) -> None:
    """Set bot commands in Telegram menu after initialization"""
    from telegram import BotCommand, BotCommandScopeChat, BotCommandScopeDefault
    commands = [
        BotCommand("start",    "🏠 Start & help menu"),
        BotCommand("post",     "✍️ Generate a LinkedIn post now"),
        BotCommand("last",     "📄 Show last post"),
        BotCommand("schedule", "📅 View/change posting schedule"),
        BotCommand("topic",    "💡 Change post topic"),
        BotCommand("style",    "🎨 Change image style"),
        BotCommand("video",    "🎬 Generate a video post"),
        BotCommand("jarvis",   "🎙 Talk to JARVIS AI"),
        BotCommand("nexus",    "🔷 NEXUS status briefing"),
        BotCommand("analytics","📊 View post analytics"),
        BotCommand("restart",  "🔄 Restart the bot"),
        BotCommand("cortex",   "🔷 CORTEX goal orchestrator"),
        BotCommand("argus",    "👁️ ARGUS system monitor"),
        BotCommand("sigma",   "SIGMA trading: status, report, positions, run"),
        BotCommand("learn",   "NEXUS-LEARN: knowledge domains & division context"),
        BotCommand("shield",  "SHIELD: security audit & access log"),
        BotCommand("phoenix", "PHOENIX: system health & restart"),
        BotCommand("phone",   "JARVIS phone interface status"),
        # Cloud commands
        BotCommand("status",  "📊 System status (services, memory, disk)"),
        BotCommand("stats",   "📈 Bot statistics"),
        BotCommand("logs",    "📋 View recent logs"),
        BotCommand("search",  "🔍 Search news & generate post"),
        BotCommand("budget",  "💰 API cost tracking & limits"),
        BotCommand("ai",      "🤖 Ask AI (smart model routing)"),
        BotCommand("run",     "⚡ Run shell command remotely"),
        BotCommand("view",    "📄 View file contents"),
        BotCommand("edit",    "✏️ Edit file remotely"),
    ]
    # Set for default scope (all chats)
    await application.bot.set_my_commands(commands, scope=BotCommandScopeDefault())
    # Set specifically for owner chat to ensure visibility
    try:
        await application.bot.set_my_commands(
            commands,
            scope=BotCommandScopeChat(chat_id=TELEGRAM_CHAT_ID)
        )
        print(f"✅ Commands set for owner chat {TELEGRAM_CHAT_ID}")
    except Exception as e:
        print(f"Warning: Could not set chat-specific commands: {e}")
    print("✅ Telegram bot commands menu updated!")


async def check_owner(update: Update) -> bool:
    """Verify the message sender is the bot owner. Silent reject otherwise."""
    user = update.effective_user
    if user and user.id == TELEGRAM_CHAT_ID:
        return True
    if update.message:
        logger.warning("Unauthorized access attempt: user_id=%s", user.id if user else "?")
    return False


async def cmd_sigma(update, context):
    """SIGMA v0.1 trading: /sigma | /sigma report | /sigma positions | /sigma run"""
    if not await check_owner(update):
        return
    arg = " ".join(context.args).lower().strip() if context.args else ""
    try:
        import sys as _sys
        _sys.path.insert(0, str(NEXUS_DIR / "divisions" / "tier3-intelligence" / "sigma"))
        from sigma import get_sigma_engine
        eng = get_sigma_engine()
        if not arg or arg == "status":
            report = eng.format_telegram_report(detailed=False)
        elif arg == "report":
            report = eng.format_telegram_report(detailed=True)
        elif arg == "positions":
            report = eng.get_open_positions_text()
        elif arg == "run":
            result = await eng.run_cycle()
            lines = ["⚡ *SIGMA Cycle Complete*"]
            for c in result.get("cycles", []):
                lines.append("%s: %s" % (c.get("pair", "?"), c.get("action", "HOLD")))
            report = "\n".join(lines)
        else:
            report = (
                "\U0001f4c8 *SIGMA Commands*\n"
                "`/sigma` \u2014 Status & P&L\n"
                "`/sigma report` \u2014 Detailed + live signals\n"
                "`/sigma positions` \u2014 Open positions\n"
                "`/sigma run` \u2014 Manual trading cycle"
            )
    except Exception as e:
        report = "\u274c SIGMA error: %s" % str(e)
    await update.message.reply_text(report, parse_mode="Markdown")


async def sigma_auto_cycle(context):
    """Auto-run SIGMA trading cycle every 4 hours"""
    try:
        import sys as _sys, os as _os
        _sys.path.insert(0, str(NEXUS_DIR / "divisions" / "tier3-intelligence" / "sigma"))
        from sigma import get_sigma_engine
        eng = get_sigma_engine()
        result = await eng.run_cycle()
        if result.get("target_hit"):
            oid = int(_os.getenv("OWNER_CHAT_ID", "0"))
            if oid:
                await context.bot.send_message(
                    chat_id=oid,
                    text="\U0001f680 *SIGMA ALERT*: 20% profit reached! LIVE trading ready!",
                    parse_mode="Markdown"
                )
    except Exception as e:
        logger.error("sigma_auto_cycle: %s", e)

async def cmd_learn(update, context):
    """NEXUS-LEARN: /learn | /learn <DIVISION>"""
    if not await check_owner(update):
        return
    arg = ' '.join(context.args).strip().upper() if context.args else ''
    try:
        import sys as _sys
        _sys.path.insert(0, str(NEXUS_DIR / 'divisions' / 'tier3-intelligence' / 'nexus-learn'))
        if 'nexus_learn' in _sys.modules:
            del _sys.modules['nexus_learn']
        from nexus_learn import get_nexus_learn
        learn = get_nexus_learn()
        if not arg or arg == 'STATUS':
            report = learn.format_telegram_status()
        else:
            knowledge = learn.get_knowledge_for_division(arg)
            stats = learn.get_stats()
            preview = (knowledge[:800] + '...') if len(knowledge) > 800 else knowledge
            report = (
                '\\*NEXUS-LEARN: ' + arg + '\\*\\n\\n' +
                preview + '\\n\\n' +
                f'_Batches: {stats["total_batches"]} | Lines: {stats["total_lines"]:,}_'
            )
    except Exception as _e:
        report = f'NEXUS-LEARN error: {_e}'
    await update.message.reply_text(report, parse_mode='Markdown')




async def cmd_shield(update, context):
    """SHIELD security audit: /shield"""
    if not await check_owner(update):
        return
    sys.path.insert(0, str(NEXUS_DIR / "divisions" / "tier4-protect" / "shield"))
    if "shield" in sys.modules: del sys.modules["shield"]
    from shield import get_shield
    s = get_shield()
    s.log_action(
        update.effective_user.id,
        update.effective_user.username or "",
        "/shield", True
    )
    report = s.get_security_report()
    await update.message.reply_text(report, parse_mode="Markdown")


async def cmd_phoenix(update, context):
    """PHOENIX health: /phoenix | /phoenix restart"""
    if not await check_owner(update):
        return
    sys.path.insert(0, str(NEXUS_DIR / "divisions" / "tier4-protect" / "phoenix"))
    if "phoenix" in sys.modules: del sys.modules["phoenix"]
    from phoenix import get_phoenix
    p = get_phoenix()
    arg = " ".join(context.args).strip().lower() if context.args else ""
    if arg == "restart":
        p.restart_all()
        await update.message.reply_text(
            "🔥 PHOENIX initiating full system restart... Stand by, sir.",
            parse_mode="Markdown"
        )
    else:
        report = p.get_health_report()
        await update.message.reply_text(report, parse_mode="Markdown")


async def cmd_phone(update, context):
    """JARVIS Phone v0.3 status: /phone"""
    if not await check_owner(update):
        return
    try:
        req  = urllib.request.urlopen("http://localhost:7863/voice/status", timeout=2)
        data = json.loads(req.read())
        twilio_ok = data.get("twilio_ready", False)
        t_icon = "✅" if twilio_ok else "⚙️"
        t_text = "Ready" if twilio_ok else "Needs API key"
        report = (
            "📞 *JARVIS Phone v0.3*\n\n"
            + f"{t_icon} Twilio: {t_text}\n"
            + "🏙 Voice: Amazon Polly Brian (en-GB)\n"
            + "🟢 Server: Online (port 7863)\n\n"
            + "*To enable real calls:*\n"
            + "1. Get Twilio account (free $15 credit)\n"
            + "2. Buy phone number (~$1/mo)\n"
            + "3. Set webhook to your tunnel URL\n"
            + "4. Tell me your Twilio credentials\n\n"
            + "_When ready: you call → JARVIS answers → live conversation_"
        )
    except Exception:
        report = (
            "📞 *JARVIS Phone v0.3*\n\n"
            + "⚠️ Phone server offline\n"
            + "Use /phoenix restart to bring all systems online"
        )
    await update.message.reply_text(report, parse_mode="Markdown")
def run_bot():
    init_db()
    app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()

    # Edit-text conversation handler
    edit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_callback, pattern=r"^edittext_")],
        states={
            WAITING_EDIT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & OWNER_FILTER,
                    handle_edit_instruction
                )
            ]
        },
        fallbacks=[]
    )

    # Analytics conversation handler
    analytics_conv = ConversationHandler(
        entry_points=[CommandHandler("analytics", cmd_analytics, filters=OWNER_FILTER)],
        states={
            WAITING_ANALYTICS: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & OWNER_FILTER,
                    handle_analytics_input
                )
            ]
        },
        fallbacks=[]
    )

    # Command handlers (owner only)
    app.add_handler(CommandHandler("start",    cmd_start,    filters=OWNER_FILTER))
    app.add_handler(CommandHandler("help",     cmd_start,    filters=OWNER_FILTER))
    app.add_handler(CommandHandler("post",     cmd_post,     filters=OWNER_FILTER))
    app.add_handler(CommandHandler("last",     cmd_last,     filters=OWNER_FILTER))
    app.add_handler(CommandHandler("schedule", cmd_schedule, filters=OWNER_FILTER))
    app.add_handler(CommandHandler("topic",   cmd_topic,    filters=OWNER_FILTER))
    app.add_handler(CommandHandler("style",   cmd_style,    filters=OWNER_FILTER))
    app.add_handler(CommandHandler("video",   cmd_video,    filters=OWNER_FILTER))
    app.add_handler(CommandHandler("jarvis",  cmd_jarvis,   filters=OWNER_FILTER))
    app.add_handler(CommandHandler("restart", cmd_restart,  filters=OWNER_FILTER))
    app.add_handler(CommandHandler("cortex",  cmd_cortex,   filters=OWNER_FILTER))
    app.add_handler(CommandHandler("argus",   cmd_argus,    filters=OWNER_FILTER))
    app.add_handler(CommandHandler("sigma", cmd_sigma, filters=OWNER_FILTER))
    app.add_handler(CommandHandler("learn", cmd_learn, filters=OWNER_FILTER))
    app.add_handler(CommandHandler("shield",  cmd_shield,  filters=OWNER_FILTER))
    app.add_handler(CommandHandler("phoenix", cmd_phoenix, filters=OWNER_FILTER))
    app.add_handler(CommandHandler("phone",   cmd_phone,   filters=OWNER_FILTER))
    app.add_handler(CommandHandler("nexus",   cmd_nexus,    filters=OWNER_FILTER))

    # ── Cloud Commands (remote control, monitoring, AI) ──────────────
    app.add_handler(CommandHandler("status",  cmd_cloud_status,  filters=OWNER_FILTER))
    app.add_handler(CommandHandler("stats",   cmd_cloud_stats,   filters=OWNER_FILTER))
    app.add_handler(CommandHandler("logs",    cmd_cloud_logs,    filters=OWNER_FILTER))
    app.add_handler(CommandHandler("search",  cmd_cloud_search,  filters=OWNER_FILTER))
    app.add_handler(CommandHandler("run",     cmd_cloud_run,     filters=OWNER_FILTER))
    app.add_handler(CommandHandler("view",    cmd_cloud_view,    filters=OWNER_FILTER))
    app.add_handler(CommandHandler("edit",    cmd_cloud_edit,    filters=OWNER_FILTER))
    app.add_handler(CommandHandler("budget",  cmd_cloud_budget,  filters=OWNER_FILTER))
    app.add_handler(CommandHandler("ai",      cmd_cloud_ai,      filters=OWNER_FILTER))

    app.add_handler(edit_conv)
    app.add_handler(analytics_conv)
    app.add_handler(CallbackQueryHandler(button_callback))

    # Cloud command callbacks (run/edit confirmations)
    app.add_handler(CallbackQueryHandler(cloud_callback_handler, pattern="^(run_|edit_)"))

    # Reply keyboard text messages
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & OWNER_FILTER,
        handle_text
    ))

    # Voice message handler (owner only)
    app.add_handler(MessageHandler(
        filters.VOICE & OWNER_FILTER,
        handle_voice
    ))

    # Silent catch-all for unauthorized users (must be last)
    app.add_handler(MessageHandler(~OWNER_FILTER, unauthorized_handler))
    app.add_handler(MessageHandler(filters.COMMAND & ~OWNER_FILTER, unauthorized_handler))

    # Schedule daily post
    app.job_queue.run_daily(
        job_daily_post,
        time=dt_time(hour=SCHEDULE_HOUR, minute=SCHEDULE_MINUTE),
        name="daily_linkedin_post"
    )

    # Sunday 8PM weekly topic suggestion
    app.job_queue.run_daily(
        job_weekly_topic_suggestion,
        time=dt_time(hour=20, minute=0),
        days=(6,),
        name="weekly_topic_suggestion"
    )

    # ARGUS daily system + cost report at 09:00 UTC
    if _get_argus is not None:
        app.job_queue.run_daily(
            _get_argus().daily_report,
            time=dt_time(hour=9, minute=0),
            name="argus_daily_report"
        )
    app.job_queue.run_repeating(sigma_auto_cycle, interval=4*3600, first=60)

    print(f"🤖 LinkedIn Bot started! Daily post at {SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d}")
    print(f"🔒 Security: ONLY chat_id {TELEGRAM_CHAT_ID} can interact")
    print("Send /post to generate a post now!")

    # Global error handler — prevents "No error handlers are registered" noise
    async def error_handler(update, context):
        logger.error("Unhandled exception: %s", context.error, exc_info=context.error)

    app.add_error_handler(error_handler)

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    run_bot()
