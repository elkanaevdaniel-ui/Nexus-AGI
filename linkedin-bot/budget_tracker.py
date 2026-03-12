"""
budget_tracker.py — Cost & Budget Tracking for NEXUS
Tracks all AI API calls, costs, and provides budget reports via Telegram.
"""
import json
import sqlite3
import os
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "budget.db")


def _get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_budget_db():
    conn = _get_conn()
    conn.execute("""CREATE TABLE IF NOT EXISTS api_calls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        model_name TEXT NOT NULL,
        model_id TEXT NOT NULL,
        task_type TEXT,
        complexity TEXT,
        input_tokens INTEGER DEFAULT 0,
        output_tokens INTEGER DEFAULT 0,
        cost_usd REAL DEFAULT 0,
        latency_ms REAL DEFAULT 0,
        routing_reason TEXT,
        success INTEGER DEFAULT 1
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS budget_config (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        daily_limit REAL DEFAULT 1.0,
        monthly_limit REAL DEFAULT 20.0,
        alert_threshold REAL DEFAULT 0.8
    )""")
    # Insert default config if not exists
    conn.execute("""INSERT OR IGNORE INTO budget_config (id, daily_limit, monthly_limit, alert_threshold)
                    VALUES (1, 1.0, 20.0, 0.8)""")
    conn.commit()
    conn.close()


def record_call(model_name: str, model_id: str, cost: float,
                input_tokens: int = 0, output_tokens: int = 0,
                task_type: str = "", complexity: str = "",
                latency_ms: float = 0, routing_reason: str = "",
                success: bool = True):
    """Record an API call for budget tracking."""
    conn = _get_conn()
    conn.execute(
        """INSERT INTO api_calls
           (timestamp, model_name, model_id, task_type, complexity,
            input_tokens, output_tokens, cost_usd, latency_ms,
            routing_reason, success)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (datetime.utcnow().isoformat(), model_name, model_id, task_type,
         complexity, input_tokens, output_tokens, cost, latency_ms,
         routing_reason, 1 if success else 0)
    )
    conn.commit()
    conn.close()


def get_budget_config() -> dict:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM budget_config WHERE id=1").fetchone()
    conn.close()
    return dict(row) if row else {"daily_limit": 1.0, "monthly_limit": 20.0, "alert_threshold": 0.8}


def set_budget_limits(daily: float = None, monthly: float = None):
    conn = _get_conn()
    if daily is not None:
        conn.execute("UPDATE budget_config SET daily_limit=? WHERE id=1", (daily,))
    if monthly is not None:
        conn.execute("UPDATE budget_config SET monthly_limit=? WHERE id=1", (monthly,))
    conn.commit()
    conn.close()


def get_spending_today() -> float:
    conn = _get_conn()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    row = conn.execute(
        "SELECT COALESCE(SUM(cost_usd), 0) as total FROM api_calls WHERE DATE(timestamp)=?",
        (today,)
    ).fetchone()
    conn.close()
    return round(row["total"], 6)


def get_spending_month() -> float:
    conn = _get_conn()
    month_start = datetime.utcnow().replace(day=1).strftime("%Y-%m-%d")
    row = conn.execute(
        "SELECT COALESCE(SUM(cost_usd), 0) as total FROM api_calls WHERE DATE(timestamp)>=?",
        (month_start,)
    ).fetchone()
    conn.close()
    return round(row["total"], 6)


def get_spending_week() -> float:
    conn = _get_conn()
    week_start = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
    row = conn.execute(
        "SELECT COALESCE(SUM(cost_usd), 0) as total FROM api_calls WHERE DATE(timestamp)>=?",
        (week_start,)
    ).fetchone()
    conn.close()
    return round(row["total"], 6)


def get_budget_report() -> str:
    """Generate a formatted budget report for Telegram."""
    config = get_budget_config()
    today_spent = get_spending_today()
    week_spent = get_spending_week()
    month_spent = get_spending_month()

    daily_pct = (today_spent / config["daily_limit"] * 100) if config["daily_limit"] > 0 else 0
    monthly_pct = (month_spent / config["monthly_limit"] * 100) if config["monthly_limit"] > 0 else 0

    # Get model breakdown for this month
    conn = _get_conn()
    month_start = datetime.utcnow().replace(day=1).strftime("%Y-%m-%d")
    models = conn.execute(
        """SELECT model_name, COUNT(*) as calls, SUM(cost_usd) as cost,
                  SUM(input_tokens) as inp, SUM(output_tokens) as outp
           FROM api_calls WHERE DATE(timestamp)>=?
           GROUP BY model_name ORDER BY cost DESC LIMIT 5""",
        (month_start,)
    ).fetchall()

    total_calls = conn.execute(
        "SELECT COUNT(*) FROM api_calls WHERE DATE(timestamp)>=?",
        (month_start,)
    ).fetchone()[0]
    conn.close()

    # Build report
    daily_bar = _progress_bar(daily_pct)
    monthly_bar = _progress_bar(monthly_pct)

    report = (
        "💰 *NEXUS Budget Report*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📅 *Today*: ${today_spent:.4f} / ${config['daily_limit']:.2f}\n"
        f"   {daily_bar} {daily_pct:.1f}%\n\n"
        f"📆 *This Week*: ${week_spent:.4f}\n\n"
        f"📊 *This Month*: ${month_spent:.4f} / ${config['monthly_limit']:.2f}\n"
        f"   {monthly_bar} {monthly_pct:.1f}%\n\n"
        f"🔢 *Total API Calls*: {total_calls}\n\n"
    )

    if models:
        report += "🤖 *Model Breakdown (Month)*:\n"
        for m in models:
            report += f"  • {m['model_name']}: {m['calls']} calls, ${m['cost']:.4f}\n"

    # Alerts
    if daily_pct >= config["alert_threshold"] * 100:
        report += "\n⚠️ *Daily budget alert!* Approaching limit.\n"
    if monthly_pct >= config["alert_threshold"] * 100:
        report += "\n🚨 *Monthly budget alert!* Approaching limit.\n"

    return report


def is_over_budget() -> tuple:
    """Check if over budget. Returns (is_over, reason)."""
    config = get_budget_config()
    today_spent = get_spending_today()
    month_spent = get_spending_month()

    if today_spent >= config["daily_limit"]:
        return True, f"Daily limit ${config['daily_limit']:.2f} reached (${today_spent:.4f} spent)"
    if month_spent >= config["monthly_limit"]:
        return True, f"Monthly limit ${config['monthly_limit']:.2f} reached (${month_spent:.4f} spent)"
    return False, ""


def _progress_bar(pct: float, length: int = 10) -> str:
    filled = min(int(pct / 100 * length), length)
    return "█" * filled + "░" * (length - filled)


# Initialize on import
init_budget_db()
