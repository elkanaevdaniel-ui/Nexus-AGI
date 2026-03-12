import os
from pathlib import Path


def _load_env_file(env_path: Path) -> None:
    """Load a .env file into os.environ — works WITHOUT python-dotenv."""
    if not env_path.exists():
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


# Load .env — check master config first, then local override
_bot_dir = Path(__file__).parent
_master_env = _bot_dir.parent.parent / '.env'
_local_env = _bot_dir / '.env'

# Try python-dotenv first (better parsing), fall back to manual loader
try:
    from dotenv import load_dotenv
    if _master_env.exists():
        load_dotenv(_master_env)
    if _local_env.exists():
        load_dotenv(_local_env, override=True)
except ImportError:
    # python-dotenv not installed — use built-in loader (no dependency needed)
    _load_env_file(_master_env)
    _load_env_file(_local_env)

# ── Core Credentials ─────────────────────────────────────────────────────────
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID", "0"))

OPENROUTER_API_KEY  = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
LLM_MODEL           = os.getenv("LLM_MODEL", "anthropic/claude-3-haiku")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# Startup diagnostics — print so it shows BEFORE logging is configured
print(f"[config] .env loaded from: {_master_env} (exists={_master_env.exists()})")
print(f"[config] Keys: TELEGRAM={'SET' if TELEGRAM_TOKEN else 'EMPTY'}, "
      f"OPENROUTER={'SET' if OPENROUTER_API_KEY else 'EMPTY'}, "
      f"GOOGLE={'SET' if GOOGLE_API_KEY else 'EMPTY'}")

# Pollinations fallback (free)
IMAGE_API_URL = "https://image.pollinations.ai/prompt/{prompt}?width=1200&height=628&nologo=true"

# ── RSS Feeds ─────────────────────────────────────────────────────────────────
NEWS_FEEDS = [
    "https://feeds.feedburner.com/TheHackersNews",
    "https://www.darkreading.com/rss.xml",
    "https://krebsonsecurity.com/feed/",
    "https://feeds.wired.com/wired/category/security",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.bleepingcomputer.com/feed/",
    "https://venturebeat.com/category/ai/feed/",
]

# ── Paths ─────────────────────────────────────────────────────────────────────
_BOT_DIR = Path(__file__).parent
DB_PATH    = os.getenv("DB_PATH",    str(_BOT_DIR / "data/posts.db"))
OUTPUT_DIR = os.getenv("OUTPUT_DIR", str(_BOT_DIR / "output"))
LOG_FILE   = os.getenv("LOG_FILE",   str(_BOT_DIR / "logs/bot.log"))

# ── Scheduler ─────────────────────────────────────────────────────────────────
SCHEDULE_HOUR   = 9
SCHEDULE_MINUTE = 0

# ── Analytics & Strategy ──────────────────────────────────────────────────────
ANALYTICS_FILE = str(_BOT_DIR / "data/analytics.json")
STRATEGY_FILE  = str(_BOT_DIR / "data/strategy.json")

# ── Weekly Topics ─────────────────────────────────────────────────────────────
CURRENT_WEEKLY_TOPIC = "AI & Cybersecurity"

WEEKLY_TOPICS = [
    "AI & Cybersecurity",
    "Cybersecurity General",
    "AI Breakthroughs & Innovation",
    "Privacy & Data Protection",
    "Threat Intelligence & APTs",
    "Zero-Day Vulnerabilities",
    "Social Engineering & Phishing",
    "Cloud Security",
    "Ransomware Trends",
    "AI Ethics & Regulation",
]

# Dashboard Authentication
DASHBOARD_USER = os.getenv("DASHBOARD_USER", "admin")
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "changeme")
