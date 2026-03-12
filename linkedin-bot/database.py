import sqlite3
from config import DB_PATH
from datetime import datetime


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
        week_start TEXT UNIQUE,
        topic TEXT,
        topic_index INTEGER
    )""")
    conn.commit()
    conn.close()


def save_post(topic, article_title, article_url, post_text, image_url, image_path):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """INSERT INTO posts (created_at, topic, article_title, article_url, post_text, image_url, image_path)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (datetime.now().isoformat(), topic, article_title, article_url, post_text, image_url, image_path)
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
    conn = get_conn()
    c = conn.cursor()
    for key, value in kwargs.items():
        c.execute(f"UPDATE posts SET {key}=? WHERE id=?", (value, post_id))
    conn.commit()
    conn.close()


def get_recent_topics(limit=10):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT topic FROM posts ORDER BY created_at DESC LIMIT ?", (limit,))
    topics = [row[0] for row in c.fetchall()]
    conn.close()
    return topics


def get_all_posts(limit=50):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM posts ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_posts_by_status(status, limit=50):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM posts WHERE status=? ORDER BY created_at DESC LIMIT ?", (status, limit))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stats():
    conn = get_conn()
    c = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    week_str = datetime.now().strftime("%Y-W%W")
    c.execute("SELECT COUNT(*) FROM posts"); total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM posts WHERE status='approved'"); approved = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM posts WHERE date(created_at)=?", (today,)); today_cnt = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM posts WHERE strftime('%Y-W%W', created_at)=?", (week_str,)); week_cnt = c.fetchone()[0]
    conn.close()
    return {"total": total, "approved": approved, "today": today_cnt, "this_week": week_cnt}


def delete_post(post_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM posts WHERE id=?", (post_id,))
    conn.commit()
    conn.close()


# ── Analytics ────────────────────────────────────────────────────────────────

def save_analytics(post_id, views, likes, comments, shares, ctr, notes=""):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO analytics (post_id, date, views, likes, comments, shares, ctr, notes) VALUES (?,?,?,?,?,?,?,?)",
        (post_id, datetime.now().strftime("%Y-%m-%d"), views, likes, comments, shares, ctr, notes)
    )
    conn.commit()
    conn.close()


def get_analytics(limit=100):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT a.*, p.topic as post_topic, p.article_title
        FROM analytics a
        LEFT JOIN posts p ON a.post_id = p.id
        ORDER BY a.date DESC LIMIT ?
    """, (limit,))
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


# ── Weekly Schedule ───────────────────────────────────────────────────────────

def save_weekly_schedule(week_start, topic, topic_index):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO weekly_schedule (week_start, topic, topic_index) VALUES (?,?,?)",
        (week_start, topic, topic_index)
    )
    conn.commit()
    conn.close()


def get_current_schedule():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM weekly_schedule ORDER BY week_start DESC LIMIT 1")
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


if __name__ == "__main__":
    init_db()
    print("Database initialized OK")
