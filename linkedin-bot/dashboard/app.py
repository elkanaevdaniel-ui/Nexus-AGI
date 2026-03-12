import asyncio
import json
import os
import signal
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BOT_DIR))

from fastapi import FastAPI, Request, HTTPException, Depends, Body
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets as _secrets
from fastapi.responses import (
    HTMLResponse, StreamingResponse, JSONResponse, FileResponse
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

from config import (
    DB_PATH, LOG_FILE, OUTPUT_DIR, SCHEDULE_HOUR, SCHEDULE_MINUTE,
    NEWS_FEEDS, LLM_MODEL, DASHBOARD_USER, DASHBOARD_PASSWORD, WEEKLY_TOPICS
)
from database import (
    get_post, update_post, init_db, get_all_posts, get_posts_by_status,
    get_stats, delete_post, save_analytics, get_analytics, get_post_analytics,
    save_weekly_schedule, get_current_schedule
)

# ── Security: HTTP Basic Auth ─────────────────────────────────────────────────
_security = HTTPBasic()


def _verify(creds: HTTPBasicCredentials = Depends(_security)):
    ok_user = _secrets.compare_digest(creds.username.encode(), DASHBOARD_USER.encode())
    ok_pass = _secrets.compare_digest(creds.password.encode(), DASHBOARD_PASSWORD.encode())
    if not (ok_user and ok_pass):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": 'Basic realm="LinkedIn Bot Dashboard"'},
        )
    return creds


app = FastAPI(title="LinkedIn Bot Dashboard", dependencies=[Depends(_verify)])
templates = Jinja2Templates(
    directory=str(BOT_DIR / "dashboard" / "templates")
)
app.mount("/output", StaticFiles(directory=OUTPUT_DIR), name="output")

BOT_PID_FILE = "/tmp/linkedin_bot.pid"
LOG_PATH = LOG_FILE

# ── Daily styles map (mirrors image_gen.py) ───────────────────────────────────
DAILY_STYLES = {
    0: "photorealistic", 1: "anime",     2: "cartoon",
    3: "watercolor",    4: "cyberpunk",  5: "3d-cgi",  6: "infographic",
}
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_bot_status():
    try:
        pid = int(open(BOT_PID_FILE).read().strip())
        os.kill(pid, 0)
        return {"running": True, "pid": pid}
    except Exception:
        return {"running": False, "pid": None}


def get_tunnel_url() -> str:
    tunnel_file = str(BOT_DIR / "logs" / "tunnel_url.txt")
    try:
        return open(tunnel_file).read().strip()
    except Exception:
        return ""


# ── Main dashboard page ───────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ── Bot control ───────────────────────────────────────────────────────────────

@app.get("/api/status")
async def api_status():
    return get_bot_status()


@app.post("/api/bot/start")
async def start_bot():
    status = get_bot_status()
    if status["running"]:
        return {"ok": False, "msg": "Bot already running"}
    log_f = open(LOG_FILE, "a")
    proc = subprocess.Popen(
        ["python3", "bot.py"],
        cwd=str(BOT_DIR),
        stdout=log_f, stderr=subprocess.STDOUT
    )
    open(BOT_PID_FILE, "w").write(str(proc.pid))
    return {"ok": True, "pid": proc.pid, "msg": "Bot started"}


@app.post("/api/bot/stop")
async def stop_bot():
    status = get_bot_status()
    if not status["running"]:
        return {"ok": False, "msg": "Bot not running"}
    try:
        os.kill(status["pid"], signal.SIGTERM)
        return {"ok": True, "msg": "Bot stopped"}
    except Exception as e:
        return {"ok": False, "msg": str(e)}


@app.post("/api/bot/restart")
async def restart_bot():
    status = get_bot_status()
    if status["running"]:
        try:
            os.kill(status["pid"], signal.SIGTERM)
        except Exception:
            pass
    await asyncio.sleep(2)
    log_f = open(LOG_FILE, "a")
    proc = subprocess.Popen(
        ["python3", "bot.py"],
        cwd=str(BOT_DIR),
        stdout=log_f, stderr=subprocess.STDOUT
    )
    open(BOT_PID_FILE, "w").write(str(proc.pid))
    return {"ok": True, "pid": proc.pid, "msg": "Bot restarted"}


# ── Stats ─────────────────────────────────────────────────────────────────────

@app.get("/api/stats")
async def api_stats():
    stats = get_stats()
    schedule = get_current_schedule()
    today_wd = datetime.now().weekday()
    if schedule:
        topic_idx = schedule.get("topic_index", 0)
        current_topic = schedule.get("topic", WEEKLY_TOPICS[0])
    else:
        topic_idx = datetime.now().isocalendar()[1] % len(WEEKLY_TOPICS)
        current_topic = WEEKLY_TOPICS[topic_idx]
    stats.update({
        "bot": get_bot_status(),
        "current_topic": current_topic,
        "today_style": DAILY_STYLES.get(today_wd, "photorealistic"),
        "next_post": f"{SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d} UTC",
        "tunnel_url": get_tunnel_url(),
    })
    return stats


# ── Posts ─────────────────────────────────────────────────────────────────────

@app.get("/api/posts")
async def api_posts(status: str = None, limit: int = 50):
    if status:
        return get_posts_by_status(status, limit)
    return get_all_posts(limit)


@app.get("/api/posts/{post_id}")
async def api_get_post(post_id: int):
    post = get_post(post_id)
    if not post:
        raise HTTPException(404, "Post not found")
    return post


@app.post("/api/posts/{post_id}/approve")
async def approve_post(post_id: int):
    post = get_post(post_id)
    if not post:
        raise HTTPException(404, "Post not found")
    update_post(post_id, status="approved", approved_at=datetime.now().isoformat())
    return {"ok": True, "msg": f"Post #{post_id} approved"}


@app.post("/api/posts/{post_id}/reject")
async def reject_post(post_id: int):
    post = get_post(post_id)
    if not post:
        raise HTTPException(404, "Post not found")
    update_post(post_id, status="rejected")
    return {"ok": True, "msg": f"Post #{post_id} rejected"}


@app.post("/api/posts/{post_id}/text")
async def update_post_text(post_id: int, request: Request):
    data = await request.json()
    new_text = data.get("text", "").strip()
    if not new_text:
        raise HTTPException(400, "text is required")
    update_post(post_id, post_text=new_text)
    return {"ok": True}


@app.delete("/api/posts/{post_id}")
async def api_delete_post(post_id: int):
    post = get_post(post_id)
    if not post:
        raise HTTPException(404, "Post not found")
    # Remove image file
    img = post.get("image_path", "")
    if img and os.path.exists(img):
        try:
            os.remove(img)
        except Exception:
            pass
    delete_post(post_id)
    return {"ok": True, "msg": f"Post #{post_id} deleted"}


@app.post("/api/posts/{post_id}/regenerate_image")
async def regen_image(post_id: int, request: Request):
    data = await request.json()
    style = data.get("style", "random")
    post = get_post(post_id)
    if not post:
        raise HTTPException(404, "Post not found")

    def _do_regen():
        # Import here to avoid circular issues at module load
        from image_gen import generate_image
        return generate_image(
            title=post["topic"],
            content=post["post_text"][:500],
            post_id=post_id,
            url=post.get("article_url", ""),
            force_style=style
        )

    img_path = await asyncio.get_event_loop().run_in_executor(None, _do_regen)
    if img_path:
        update_post(post_id, image_path=img_path)
        return {"ok": True, "image_path": img_path}
    return {"ok": False, "msg": "Image generation failed"}


# ── Image serving ─────────────────────────────────────────────────────────────

@app.get("/api/image/{post_id}")
async def get_image(post_id: int):
    post = get_post(post_id)
    if post and post.get("image_path") and os.path.exists(post["image_path"]):
        return FileResponse(post["image_path"], media_type="image/png")
    raise HTTPException(404, "Image not found")


# ── Generate post (FIXED signatures) ─────────────────────────────────────────

@app.post("/api/generate")
async def api_generate():
    """Trigger post generation with correct function signatures."""
    bot_path = str(BOT_DIR)
    script = f'''import sys; sys.path.insert(0, {bot_path!r})
from scraper import fetch_news, pick_best_article
from ai_writer import generate_post
from image_gen import generate_image
from database import save_post, get_recent_topics, update_post, init_db
from datetime import datetime
DAILY_STYLES = {0:"photorealistic",1:"anime",2:"cartoon",3:"watercolor",4:"cyberpunk",5:"3d-cgi",6:"infographic"}
init_db()
articles = fetch_news()
used = get_recent_topics(5)
article = pick_best_article(articles, used)
if article:
    result = generate_post(article)
    post_text = result["post_text"]
    post_id = save_post(
        topic=article["title"][:100],
        article_title=article["title"],
        article_url=article.get("url",""),
        post_text=post_text,
        image_url="",
        image_path=""
    )
    style = DAILY_STYLES.get(datetime.now().weekday(), "photorealistic")
    img_path = generate_image(
        title=article["title"],
        content=article.get("content") or article.get("summary") or "",
        post_id=post_id,
        url=article.get("url",""),
        force_style=style
    )
    if img_path:
        update_post(post_id, image_path=img_path)
    print("Post", post_id, "generated OK")
else:
    print("No article found")
'''
    subprocess.Popen(
        ["python3", "-c", script],
        cwd=str(BOT_DIR)
    )
    return {"ok": True, "msg": "Post generation started! Refresh in ~60 seconds."}


# ── Quick edit post via dashboard ─────────────────────────────────────────────

@app.post("/api/post/{post_id}/approve")
async def compat_approve(post_id: int):
    return await approve_post(post_id)


@app.post("/api/post/{post_id}/edit")
async def compat_edit(post_id: int, request: Request):
    return await update_post_text(post_id, request)


@app.get("/api/post/{post_id}/image")
async def compat_image(post_id: int):
    return await get_image(post_id)


# ── Analytics ─────────────────────────────────────────────────────────────────

@app.get("/api/analytics")
async def api_get_analytics(limit: int = 100):
    return get_analytics(limit)


@app.post("/api/analytics")
async def api_save_analytics(request: Request):
    data = await request.json()
    try:
        save_analytics(
            post_id =int(data.get("post_id",  0)),
            views   =int(data.get("views",    0)),
            likes   =int(data.get("likes",    0)),
            comments=int(data.get("comments", 0)),
            shares  =int(data.get("shares",   0)),
            ctr     =float(data.get("ctr",    0.0)),
            notes   =data.get("notes", "")
        )
        return {"ok": True}
    except Exception as e:
        raise HTTPException(400, str(e))


@app.get("/api/analytics/{post_id}")
async def api_post_analytics(post_id: int):
    return get_post_analytics(post_id)


# ── Scheduler / Topic ─────────────────────────────────────────────────────────

@app.get("/api/schedule")
async def api_schedule():
    schedule = get_current_schedule()
    today_wd = datetime.now().weekday()
    if schedule:
        topic_idx     = schedule.get("topic_index", 0)
        current_topic = schedule.get("topic", WEEKLY_TOPICS[0])
    else:
        topic_idx     = datetime.now().isocalendar()[1] % len(WEEKLY_TOPICS)
        current_topic = WEEKLY_TOPICS[topic_idx]
    calendar = [
        {
            "day":    DAY_NAMES[i],
            "style":  DAILY_STYLES.get(i, "photorealistic"),
            "hour":   SCHEDULE_HOUR,
            "minute": SCHEDULE_MINUTE,
            "today":  i == today_wd,
        }
        for i in range(7)
    ]
    return {
        "current_topic":  current_topic,
        "topic_index":    topic_idx,
        "topics":         WEEKLY_TOPICS,
        "calendar":       calendar,
        "schedule_time":  f"{SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d}",
    }


@app.post("/api/schedule/topic")
async def api_set_topic(request: Request):
    data = await request.json()
    idx = int(data.get("index", 0))
    if not 0 <= idx < len(WEEKLY_TOPICS):
        raise HTTPException(400, f"Index must be 0-{len(WEEKLY_TOPICS)-1}")
    week_start = datetime.now().strftime("%Y-W%W")
    save_weekly_schedule(week_start, WEEKLY_TOPICS[idx], idx)
    return {"ok": True, "topic": WEEKLY_TOPICS[idx]}


# ── Config ────────────────────────────────────────────────────────────────────

@app.get("/api/config")
async def api_config():
    from config import (
        TELEGRAM_CHAT_ID, OPENROUTER_API_KEY, GOOGLE_API_KEY,
        LLM_MODEL, SCHEDULE_HOUR, SCHEDULE_MINUTE, NEWS_FEEDS
    )
    def mask(s):
        if not s:
            return ""
        return s[:6] + "..." + s[-4:] if len(s) > 12 else "****"
    return {
        "telegram_chat_id":    TELEGRAM_CHAT_ID,
        "openrouter_key":      mask(OPENROUTER_API_KEY),
        "google_key":          mask(GOOGLE_API_KEY),
        "llm_model":           LLM_MODEL,
        "schedule":            f"{SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d}",
        "feeds":               NEWS_FEEDS,
        "topics":              WEEKLY_TOPICS,
    }


# ── Logs ──────────────────────────────────────────────────────────────────────

@app.get("/api/logs/stream")  # legacy SSE path
@app.get("/stream/logs")
async def stream_logs():
    async def generate():
        try:
            with open(LOG_PATH, "r") as f:
                f.seek(0, 2)  # seek to end
                while True:
                    line = f.readline()
                    if line:
                        yield f"data: {json.dumps(line.rstrip())}\n\n"
                    else:
                        await asyncio.sleep(0.5)
        except Exception as e:
            yield f"data: {json.dumps(str(e))}\n\n"
    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/api/logs")
async def api_logs(lines: int = 200):
    try:
        result = subprocess.run(
            ["tail", f"-{lines}", LOG_PATH],
            capture_output=True, text=True
        )
        return {"lines": result.stdout.splitlines()}
    except Exception:
        return {"lines": []}


@app.get("/api/logs/history")
async def api_logs_history(lines: int = 100):
    return await api_logs(lines)


@app.delete("/api/logs")
async def clear_logs():
    try:
        open(LOG_PATH, "w").close()
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/download/logs")
async def download_logs():
    if os.path.exists(LOG_PATH):
        return FileResponse(
            LOG_PATH,
            media_type="text/plain",
            filename="bot.log"
        )
    raise HTTPException(404, "Log file not found")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    print("LinkedIn Bot Dashboard running at http://localhost:7860")
    uvicorn.run(app, host="0.0.0.0", port=7860, log_level="warning")
