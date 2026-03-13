"""database.py - SQLite database layer for LinkedIn bot.

Security: All column names are validated against a whitelist to prevent SQL injection.
"""
import sqlite3
from config import DB_PATH
from datetime import datetime


# Column whitelist for SQL injection prevention
POSTS_ALLOWED_COLUMNS = frozenset({
    "topic", "article_title", "article_url", "post_text",
    "image_url", "image_path", "status", "approved_at",
})


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT,
        topic TEXT,
        article_title TEXT,
        article_url TEXT,
        post_text TEXT,
        image_url TEXT,
        image_path TEXT,
        status TEXT DEFAULT 'draft',
        approved_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS analytics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER,
        date TEXT,
        views INTEGER DEFAULT 0,
        likes INTEGER DEFAULT 0,
        comments INTEGER DEFAULT 0,
        shares INTEGER DEFAULT 0,
        ctr REAL DEFAULT 0,
        notes TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS weekly_schedule (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        week_start TEXT,
        topic TEXT,
        topic_index INTEGER,
        created_at TEXT
    )""")
    conn.commit()
    conn.close()


def save_post(topic, article_title, article_url, post_text, image_url, image_path):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO posts (created_at, topic, article_title, article_url, post_text, image_url, image_path, status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 'draft')",
        (datetime.now().isoformat(), topic, article_title, article_url, post_text, image_url, image_path),
    )
    post_id = c.lastrowid
    conn.commit()
    conn.close()
    return post_id


def get_post(post_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM posts WHERE id=?", (post_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def update_post(post_id, **kwargs):
    """Update post fields. Only whitelisted column names are allowed to prevent SQL injection."""
    conn = get_conn()
    c = conn.cursor()
    for key, value in kwargs.items():
        if key not in POSTS_ALLOWED_COLUMNS:
            conn.close()
            raise ValueError(f"Invalid column name: {key!r}. Allowed: {sorted(POSTS_ALLOWED_COLUMNS)}")
        c.execute(f"UPDATE posts SET {key}=? WHERE id=?", (value, post_id))
    conn.commit()
    conn.close()


def get_recent_topics(limit=10):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT topic FROM posts ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return [r["topic"] for r in rows]


def get_all_posts(limit=50):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM posts ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_posts_by_status(status, limit=50):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM posts WHERE status=? ORDER BY id DESC LIMIT ?", (status, limit))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stats():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as total FROM posts")
    total = c.fetchone()["total"]
    c.execute("SELECT COUNT(*) as published FROM posts WHERE status='published'")
    published = c.fetchone()["published"]
    c.execute("SELECT COUNT(*) as draft FROM posts WHERE status='draft'")
    draft = c.fetchone()["draft"]
    c.execute("SELECT COUNT(*) as approved FROM posts WHERE status='approved'")
    approved = c.fetchone()["approved"]
    conn.close()
    return {"total": total, "published": published, "draft": draft, "approved": approved}


def delete_post(post_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM posts WHERE id=?", (post_id,))
    conn.commit()
    conn.close()


def save_analytics(post_id, views, likes, comments, shares, ctr, notes=""):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO analytics (post_id, date, views, likes, comments, shares, ctr, notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (post_id, datetime.now().isoformat(), views, likes, comments, shares, ctr, notes),
    )
    conn.commit()
    conn.close()


def get_analytics(limit=100):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM analytics ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_post_analytics(post_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM analytics WHERE post_id=? ORDER BY date DESC", (post_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_weekly_schedule(week_start, topic, topic_index):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO weekly_schedule (week_start, topic, topic_index, created_at) VALUES (?, ?, ?, ?)",
        (week_start, topic, topic_index, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_current_schedule():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM weekly_schedule ORDER BY id DESC LIMIT 7")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]
