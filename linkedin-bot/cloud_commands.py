"""
cloud_commands.py — Enhanced Telegram Commands for Cloud Deployment
Adds: /status, /stats, /logs, /search, /run, /edit, /view, /budget, /ai
"""
import asyncio
import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import TELEGRAM_CHAT_ID
from budget_tracker import (
    get_budget_report, record_call, set_budget_limits,
    get_spending_today, get_spending_month, is_over_budget
)
from smart_router import call_ai, classify_task, MODELS
from remote_control import (
    is_command_safe, execute_command, view_file, edit_file, list_directory
)

logger = logging.getLogger(__name__)

BOT_DIR = Path(__file__).parent
PROJECT_DIR = BOT_DIR.parent

# ── Pending confirmations for dangerous commands ──────────────────────────────
_pending_commands = {}  # chat_id -> command string


# ══════════════════════════════════════════════════════════════════════════════
# /status — System status overview
# ══════════════════════════════════════════════════════════════════════════════

async def cmd_cloud_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show full system status: services, disk, memory, uptime."""
    msg = await update.message.reply_text("🔍 Checking system status...")

    # Gather system info
    checks = {}
    try:
        # Uptime
        result = subprocess.run(["uptime", "-p"], capture_output=True, text=True, timeout=5)
        checks["uptime"] = result.stdout.strip()
    except Exception:
        checks["uptime"] = "unknown"

    try:
        # Memory
        result = subprocess.run(["free", "-h"], capture_output=True, text=True, timeout=5)
        lines = result.stdout.strip().split("\n")
        if len(lines) >= 2:
            parts = lines[1].split()
            checks["memory"] = f"{parts[2]} used / {parts[1]} total"
        else:
            checks["memory"] = "unknown"
    except Exception:
        checks["memory"] = "unknown"

    try:
        # Disk
        result = subprocess.run(["df", "-h", "/"], capture_output=True, text=True, timeout=5)
        lines = result.stdout.strip().split("\n")
        if len(lines) >= 2:
            parts = lines[1].split()
            checks["disk"] = f"{parts[2]} used / {parts[1]} total ({parts[4]})"
        else:
            checks["disk"] = "unknown"
    except Exception:
        checks["disk"] = "unknown"

    # Service status
    services = {
        "nexus-bot": "Telegram Bot",
        "nexus-dashboard": "LinkedIn Dashboard",
        "nexus-command": "Command Center",
        "caddy": "Web Server (Caddy)",
    }
    service_lines = []
    for svc, name in services.items():
        try:
            result = subprocess.run(
                ["systemctl", "is-active", svc],
                capture_output=True, text=True, timeout=5
            )
            status = result.stdout.strip()
            icon = "🟢" if status == "active" else "🔴"
            service_lines.append(f"  {icon} {name}: {status}")
        except Exception:
            service_lines.append(f"  ⚪ {name}: unknown")

    # Budget summary
    today_spent = get_spending_today()
    month_spent = get_spending_month()

    text = (
        "📊 *NEXUS System Status*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⏱ *Uptime*: {checks['uptime']}\n"
        f"💾 *Memory*: {checks['memory']}\n"
        f"💿 *Disk*: {checks['disk']}\n\n"
        "🔧 *Services*:\n" + "\n".join(service_lines) + "\n\n"
        f"💰 *API Spend*: ${today_spent:.4f} today / ${month_spent:.4f} month\n"
    )

    await msg.edit_text(text, parse_mode="Markdown")


# ══════════════════════════════════════════════════════════════════════════════
# /stats — Bot statistics
# ══════════════════════════════════════════════════════════════════════════════

async def cmd_cloud_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot statistics: posts, engagement, API usage."""
    from database import get_stats

    stats = get_stats()
    today_spent = get_spending_today()
    month_spent = get_spending_month()

    text = (
        "📈 *NEXUS Statistics*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📝 *Posts*:\n"
        f"  Total: {stats['total']}\n"
        f"  Approved: {stats['approved']}\n"
        f"  Today: {stats['today']}\n"
        f"  This Week: {stats['this_week']}\n\n"
        "💰 *API Costs*:\n"
        f"  Today: ${today_spent:.4f}\n"
        f"  This Month: ${month_spent:.4f}\n"
    )

    await update.message.reply_text(text, parse_mode="Markdown")


# ══════════════════════════════════════════════════════════════════════════════
# /logs — View recent logs
# ══════════════════════════════════════════════════════════════════════════════

async def cmd_cloud_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent bot logs. Usage: /logs [lines] [logname]"""
    args = context.args or []
    lines = 30
    log_name = "bot.log"

    if args:
        try:
            lines = int(args[0])
        except ValueError:
            log_name = args[0]
        if len(args) > 1:
            log_name = args[1]

    log_path = BOT_DIR / "logs" / log_name
    if not log_path.exists():
        await update.message.reply_text(f"Log file not found: {log_name}")
        return

    try:
        all_lines = log_path.read_text().splitlines()
        recent = all_lines[-lines:]
        content = "\n".join(recent)
        if len(content) > 3500:
            content = content[-3500:]

        await update.message.reply_text(
            f"📋 *Last {len(recent)} lines of {log_name}*:\n\n```\n{content}\n```",
            parse_mode="Markdown"
        )
    except Exception as exc:
        await update.message.reply_text(f"Error reading logs: {exc}")


# ══════════════════════════════════════════════════════════════════════════════
# /search — Trigger LinkedIn search on demand
# ══════════════════════════════════════════════════════════════════════════════

async def cmd_cloud_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Search for news and generate a post. Usage: /search [keyword]"""
    keyword = " ".join(context.args) if context.args else None

    msg = await update.message.reply_text(
        f"🔍 Searching for news{' about: ' + keyword if keyword else ''}..."
    )

    try:
        from scraper import fetch_news, pick_best_article
        from database import get_recent_topics, init_db

        init_db()
        articles = fetch_news()

        if keyword:
            # Filter articles by keyword
            kw_lower = keyword.lower()
            articles = [a for a in articles if kw_lower in (
                a.get("title", "") + " " + a.get("summary", "")
            ).lower()]

        used = get_recent_topics(5)
        article = pick_best_article(articles, used)

        if not article:
            await msg.edit_text("No matching articles found. Try a different keyword.")
            return

        await msg.edit_text(
            f"📰 Found: *{article['title'][:100]}*\n\nGenerating post...",
            parse_mode="Markdown"
        )

        # Generate post using smart router
        result = call_ai(
            prompt=f"Write a viral LinkedIn post about: {article['title']}\n\nContent: {article.get('content', article.get('summary', ''))[:2000]}",
            system="You are an elite LinkedIn content strategist. Write a viral post with pattern interrupts, engagement magnets, and 5-7 hashtags. 250-400 words.",
        )

        # Record cost
        record_call(
            model_name=result["model"],
            model_id=result["model_id"],
            cost=result["cost"],
            input_tokens=result["tokens"]["input"],
            output_tokens=result["tokens"]["output"],
            task_type="creative",
            complexity="moderate",
            latency_ms=result["latency_ms"],
            routing_reason=result["routing"],
        )

        await msg.edit_text(
            f"📝 *Generated Post*\n\n{result['text'][:3500]}\n\n"
            f"🤖 Model: {result['model']} | 💰 ${result['cost']:.4f}",
            parse_mode="Markdown"
        )

    except Exception as exc:
        logger.error("Search failed: %s", exc)
        await msg.edit_text(f"Search failed: {exc}")


# ══════════════════════════════════════════════════════════════════════════════
# /run — Execute shell commands remotely
# ══════════════════════════════════════════════════════════════════════════════

async def cmd_cloud_run(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Run a shell command on the server. Usage: /run <command>"""
    if not context.args:
        await update.message.reply_text(
            "Usage: `/run <command>`\n"
            "Example: `/run ls -la`\n"
            "Example: `/run df -h`\n"
            "Example: `/run systemctl status nexus-bot`",
            parse_mode="Markdown"
        )
        return

    command = " ".join(context.args)
    is_safe, needs_confirm, reason = is_command_safe(command)

    if not is_safe:
        await update.message.reply_text(f"🚫 {reason}")
        return

    if needs_confirm:
        _pending_commands[update.effective_chat.id] = command
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Confirm", callback_data="run_confirm"),
                InlineKeyboardButton("❌ Cancel", callback_data="run_cancel"),
            ]
        ])
        await update.message.reply_text(
            f"⚠️ *Dangerous command detected*\n\n"
            f"```\n{command}\n```\n\n"
            f"Reason: {reason}\n\n"
            f"Do you want to proceed?",
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
        return

    # Execute directly
    msg = await update.message.reply_text(f"⚡ Running: `{command}`...", parse_mode="Markdown")
    result = await execute_command(command)

    output = result["output"] or result["error"] or "(no output)"
    icon = "✅" if result["return_code"] == 0 else "❌"

    await msg.edit_text(
        f"{icon} Exit code: {result['return_code']}\n\n```\n{output[:3500]}\n```",
        parse_mode="Markdown"
    )


async def handle_run_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle confirmation callbacks for dangerous commands."""
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat_id
    command = _pending_commands.pop(chat_id, None)

    if query.data == "run_cancel":
        await query.edit_message_text("❌ Command cancelled.")
        return

    if query.data == "run_confirm" and command:
        await query.edit_message_text(f"⚡ Running: `{command}`...", parse_mode="Markdown")
        result = await execute_command(command)
        output = result["output"] or result["error"] or "(no output)"
        icon = "✅" if result["return_code"] == 0 else "❌"
        await query.edit_message_text(
            f"{icon} Exit code: {result['return_code']}\n\n```\n{output[:3500]}\n```",
            parse_mode="Markdown"
        )


# ══════════════════════════════════════════════════════════════════════════════
# /view — View file contents
# ══════════════════════════════════════════════════════════════════════════════

async def cmd_cloud_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View a file's contents. Usage: /view <filepath>"""
    if not context.args:
        # Show directory listing
        result = list_directory()
        if result["error"]:
            await update.message.reply_text(f"Error: {result['error']}")
            return

        text = "📂 *Project Files*:\n\n"
        for f in result["files"][:30]:
            icon = "📁" if f["type"] == "dir" else "📄"
            size = f" ({f['size']}b)" if f["type"] == "file" else ""
            text += f"  {icon} {f['name']}{size}\n"

        text += "\nUsage: `/view <filepath>`"
        await update.message.reply_text(text, parse_mode="Markdown")
        return

    filepath = " ".join(context.args)
    # If relative path, resolve from project dir
    if not filepath.startswith("/"):
        filepath = str(PROJECT_DIR / filepath)

    result = view_file(filepath)
    if result["error"]:
        await update.message.reply_text(f"❌ {result['error']}")
        return

    content = result["content"]
    if len(content) > 3500:
        content = content[:3500] + "\n... (truncated)"

    await update.message.reply_text(
        f"📄 *{filepath}* ({result['size']} bytes)\n\n```\n{content}\n```",
        parse_mode="Markdown"
    )


# ══════════════════════════════════════════════════════════════════════════════
# /edit — Edit file contents
# ══════════════════════════════════════════════════════════════════════════════

async def cmd_cloud_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Edit a file. Usage: /edit <filepath>\n<new content>"""
    if not context.args:
        await update.message.reply_text(
            "Usage: `/edit <filepath>`\n"
            "Then send the new content as the next message.\n\n"
            "Or: `/edit <filepath> <content>`\n"
            "To replace the entire file in one command.",
            parse_mode="Markdown"
        )
        return

    # Parse: first arg is filepath, rest is content
    full_text = update.message.text[len("/edit "):].strip()
    parts = full_text.split("\n", 1)

    filepath = parts[0].strip()
    if not filepath.startswith("/"):
        filepath = str(PROJECT_DIR / filepath)

    if len(parts) > 1:
        content = parts[1]
        # Confirm before editing
        _pending_commands[update.effective_chat.id] = f"EDIT:{filepath}:{content}"
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Save", callback_data="edit_confirm"),
                InlineKeyboardButton("❌ Cancel", callback_data="edit_cancel"),
            ]
        ])
        preview = content[:500] + ("..." if len(content) > 500 else "")
        await update.message.reply_text(
            f"📝 *Edit file*: `{filepath}`\n\n"
            f"*New content preview*:\n```\n{preview}\n```\n\n"
            f"Save changes?",
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
    else:
        # Show current content and ask for new content
        result = view_file(filepath)
        if result["error"]:
            await update.message.reply_text(f"❌ {result['error']}")
            return

        content = result["content"][:2000]
        await update.message.reply_text(
            f"📄 Current content of `{filepath}`:\n\n```\n{content}\n```\n\n"
            f"Send the new content as your next message.",
            parse_mode="Markdown"
        )
        # Store filepath for next message handling
        context.user_data["pending_edit_file"] = filepath


async def handle_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle edit confirmation callbacks."""
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat_id
    pending = _pending_commands.pop(chat_id, None)

    if query.data == "edit_cancel":
        await query.edit_message_text("❌ Edit cancelled.")
        return

    if query.data == "edit_confirm" and pending and pending.startswith("EDIT:"):
        parts = pending[5:].split(":", 1)
        filepath = parts[0]
        content = parts[1] if len(parts) > 1 else ""

        result = edit_file(filepath, content)
        if result["success"]:
            await query.edit_message_text(f"✅ File saved: `{filepath}`", parse_mode="Markdown")
        else:
            await query.edit_message_text(f"❌ Error: {result['error']}")


# ══════════════════════════════════════════════════════════════════════════════
# /budget — Cost tracking and budget management
# ══════════════════════════════════════════════════════════════════════════════

async def cmd_cloud_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show budget report or set limits. Usage: /budget [set daily|monthly <amount>]"""
    args = context.args or []

    if args and args[0] == "set":
        if len(args) < 3:
            await update.message.reply_text(
                "Usage:\n"
                "  `/budget set daily 2.00`\n"
                "  `/budget set monthly 30.00`",
                parse_mode="Markdown"
            )
            return

        try:
            amount = float(args[2])
            if args[1] == "daily":
                set_budget_limits(daily=amount)
                await update.message.reply_text(f"✅ Daily budget set to ${amount:.2f}")
            elif args[1] == "monthly":
                set_budget_limits(monthly=amount)
                await update.message.reply_text(f"✅ Monthly budget set to ${amount:.2f}")
            else:
                await update.message.reply_text("Use: `/budget set daily <amount>` or `/budget set monthly <amount>`", parse_mode="Markdown")
        except ValueError:
            await update.message.reply_text("Invalid amount. Use a number like 2.50")
        return

    # Show budget report
    report = get_budget_report()
    await update.message.reply_text(report, parse_mode="Markdown")


# ══════════════════════════════════════════════════════════════════════════════
# /ai — Direct AI query with smart routing
# ══════════════════════════════════════════════════════════════════════════════

async def cmd_cloud_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask AI anything with smart model routing. Usage: /ai <question>"""
    if not context.args:
        models_text = "\n".join(f"  • `{k}`: {v['name']}" for k, v in MODELS.items())
        await update.message.reply_text(
            "🤖 *Smart AI Query*\n\n"
            "Usage: `/ai <question>`\n"
            "Force model: `/ai --model premium <question>`\n\n"
            f"*Available models*:\n{models_text}\n\n"
            "The router automatically picks the cheapest capable model.",
            parse_mode="Markdown"
        )
        return

    # Check budget
    over, reason = is_over_budget()
    if over:
        await update.message.reply_text(f"🚫 Budget exceeded: {reason}\nUse `/budget set` to increase limits.", parse_mode="Markdown")
        return

    args = list(context.args)
    force_model = None

    # Check for --model flag
    if "--model" in args:
        idx = args.index("--model")
        if idx + 1 < len(args):
            force_model = args[idx + 1]
            args = args[:idx] + args[idx + 2:]

    prompt = " ".join(args)
    msg = await update.message.reply_text("🧠 Thinking...")

    result = call_ai(prompt, force_model=force_model)

    # Record to budget tracker
    record_call(
        model_name=result["model"],
        model_id=result["model_id"],
        cost=result["cost"],
        input_tokens=result["tokens"]["input"],
        output_tokens=result["tokens"]["output"],
        task_type="query",
        latency_ms=result["latency_ms"],
        routing_reason=result["routing"],
    )

    response_text = result["text"]
    if len(response_text) > 3500:
        response_text = response_text[:3500] + "..."

    footer = f"\n\n🤖 {result['model']} | 💰 ${result['cost']:.4f} | ⚡ {result['latency_ms']:.0f}ms"

    await msg.edit_text(response_text + footer)


# ══════════════════════════════════════════════════════════════════════════════
# Callback router for all cloud commands
# ══════════════════════════════════════════════════════════════════════════════

async def cloud_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route callback queries for cloud commands."""
    query = update.callback_query
    data = query.data

    if data in ("run_confirm", "run_cancel"):
        await handle_run_callback(update, context)
    elif data in ("edit_confirm", "edit_cancel"):
        await handle_edit_callback(update, context)
