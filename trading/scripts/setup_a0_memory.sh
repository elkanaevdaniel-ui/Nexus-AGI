#!/usr/bin/env bash
# ==============================================================================
# setup_a0_memory.sh — Initialize Agent Zero's structured memory (SQLite + Redis)
# ==============================================================================
# Run once on EC2: bash ~/polymarket-agent/scripts/setup_a0_memory.sh
# ==============================================================================

set -e

DB_DIR="$HOME/polymarket-agent/data"
DB_PATH="$DB_DIR/a0_memory.db"
JOURNAL_DIR="$DB_DIR/journals"

echo "=== Setting up Agent Zero Memory System ==="

# Create directories
mkdir -p "$DB_DIR" "$JOURNAL_DIR"

# Create SQLite database with schema
sqlite3 "$DB_PATH" <<'SQL'

-- Trade journal: every trade outcome
CREATE TABLE IF NOT EXISTS trade_journal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    market TEXT NOT NULL,
    market_id TEXT,
    direction TEXT NOT NULL,          -- BUY_YES, BUY_NO, SELL_YES, SELL_NO
    price REAL NOT NULL,              -- Entry price (0-1)
    size REAL NOT NULL,               -- Dollar amount
    edge REAL,                        -- Estimated edge at entry
    our_estimate REAL,                -- Our probability estimate
    market_price REAL,                -- Market price at entry
    outcome TEXT,                     -- WIN, LOSS, PENDING, CANCELLED
    pnl REAL,                         -- Profit/loss in dollars
    reasoning TEXT,                   -- Why we took the trade
    lesson TEXT,                      -- What we learned (filled after resolution)
    confidence_score REAL,            -- 0-1 how confident we were
    tags TEXT,                        -- Comma-separated: election,politics,crypto
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
);

-- Lessons learned from trades and operations
CREATE TABLE IF NOT EXISTS lessons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    category TEXT NOT NULL,           -- trade, code, strategy, market, system
    title TEXT NOT NULL,
    lesson TEXT NOT NULL,
    source TEXT,                      -- What triggered this lesson
    severity TEXT DEFAULT 'info',     -- info, warning, critical
    tags TEXT,                        -- Comma-separated searchable tags
    applied INTEGER DEFAULT 0,        -- 1 if we've adjusted strategy based on this
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Daily summaries (auto-generated journals)
CREATE TABLE IF NOT EXISTS daily_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL UNIQUE,
    trades_count INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    total_pnl REAL DEFAULT 0,
    portfolio_value REAL,
    best_trade TEXT,                   -- JSON: {market, pnl}
    worst_trade TEXT,                  -- JSON: {market, pnl}
    key_lessons TEXT,                  -- Summary of lessons learned
    strategy_notes TEXT,               -- Strategy adjustments
    tomorrow_focus TEXT,               -- What to focus on tomorrow
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Strategy updates (weekly reviews + adjustments)
CREATE TABLE IF NOT EXISTS strategy_updates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    period TEXT NOT NULL,              -- daily, weekly, monthly
    win_rate REAL,
    avg_edge REAL,
    avg_pnl REAL,
    total_trades INTEGER,
    calibration_score REAL,            -- How accurate our estimates are
    adjustments TEXT,                  -- What we're changing
    market_types_good TEXT,            -- JSON: types we do well on
    market_types_bad TEXT,             -- JSON: types we do poorly on
    confidence_multiplier REAL DEFAULT 1.0,  -- Adjust future confidence
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Market watchlist
CREATE TABLE IF NOT EXISTS watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id TEXT NOT NULL,
    market_question TEXT NOT NULL,
    current_price REAL,
    our_estimate REAL,
    alert_threshold REAL DEFAULT 0.05, -- Alert if price moves > 5%
    alert_type TEXT DEFAULT 'price_move', -- price_move, resolution, volume_spike
    webhook_url TEXT,                  -- Optional webhook for external alerts
    active INTEGER DEFAULT 1,
    notes TEXT,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_checked TIMESTAMP,
    last_alert_at TIMESTAMP
);

-- Confidence calibration tracking
CREATE TABLE IF NOT EXISTS calibration (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    edge_bucket TEXT NOT NULL,         -- low (0-5%), medium (5-10%), high (10%+)
    total_trades INTEGER,
    wins INTEGER,
    actual_win_rate REAL,
    expected_win_rate REAL,
    brier_score REAL,                  -- Lower is better
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Session logs (track A0 usage patterns)
CREATE TABLE IF NOT EXISTS session_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_start TIMESTAMP NOT NULL,
    session_end TIMESTAMP,
    claude_calls INTEGER DEFAULT 0,
    workflows_run TEXT,                -- JSON: list of workflows executed
    trades_approved INTEGER DEFAULT 0,
    trades_rejected INTEGER DEFAULT 0,
    errors TEXT,                       -- JSON: any errors during session
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_trade_journal_date ON trade_journal(date);
CREATE INDEX IF NOT EXISTS idx_trade_journal_outcome ON trade_journal(outcome);
CREATE INDEX IF NOT EXISTS idx_trade_journal_market ON trade_journal(market_id);
CREATE INDEX IF NOT EXISTS idx_lessons_category ON lessons(category);
CREATE INDEX IF NOT EXISTS idx_lessons_tags ON lessons(tags);
CREATE INDEX IF NOT EXISTS idx_watchlist_active ON watchlist(active);
CREATE INDEX IF NOT EXISTS idx_daily_summaries_date ON daily_summaries(date);

SQL

echo "SQLite database created at: $DB_PATH"

# Show tables
echo ""
echo "=== Tables Created ==="
sqlite3 "$DB_PATH" ".tables"

# Verify Redis is available
if command -v redis-cli &>/dev/null; then
    if redis-cli ping 2>/dev/null | grep -q PONG; then
        echo ""
        echo "=== Redis Status ==="
        echo "Redis: CONNECTED"
        # Set initial keys
        redis-cli SET a0:session_start "$(date -Iseconds)" EX 86400 >/dev/null
        redis-cli SET a0:version "2.0-enhanced" EX 86400 >/dev/null
        echo "Initial Redis keys set"
    else
        echo "Redis: NOT RUNNING (start with: sudo systemctl start redis)"
    fi
else
    echo "Redis CLI: NOT INSTALLED (install with: sudo apt install redis-tools)"
fi

echo ""
echo "=== Memory System Ready ==="
echo "SQLite: $DB_PATH"
echo "Journals: $JOURNAL_DIR"
echo "Redis: localhost:6379 (prefix: a0:)"
echo ""
echo "Done!"
