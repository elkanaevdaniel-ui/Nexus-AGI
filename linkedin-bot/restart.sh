#!/bin/bash
# ── Safe LinkedIn Bot Restart Script ─────────────────────────────────────────
# Stops ALL process managers (PM2, systemd) that may respawn bot.py,
# kills ALL bot processes (including ghost processes from old venvs),
# waits for Telegram to release the long-poll lock, then starts a single
# clean instance.
#
# Usage: bash ~/ai-projects/linkedin-bot/restart.sh
# ─────────────────────────────────────────────────────────────────────────────

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_FILE="/tmp/bot-startup.log"
VENV="$SCRIPT_DIR/venv/bin/activate"

echo "=== LinkedIn Bot Safe Restart ==="
echo ""

# ── Step 0: Stop process managers that respawn bot.py ────────────────────────
echo "[0/6] Stopping process managers..."
# systemd
if systemctl is-active nexus-bot.service >/dev/null 2>&1; then
    sudo systemctl stop nexus-bot.service 2>/dev/null && echo "  Stopped nexus-bot.service"
    sudo systemctl disable nexus-bot.service 2>/dev/null && echo "  Disabled nexus-bot.service"
elif systemctl is-enabled nexus-bot.service >/dev/null 2>&1; then
    sudo systemctl disable nexus-bot.service 2>/dev/null && echo "  Disabled nexus-bot.service"
else
    echo "  nexus-bot.service: not active"
fi
# PM2
if command -v pm2 >/dev/null 2>&1; then
    pm2 stop nexus-bot 2>/dev/null && echo "  Stopped PM2 nexus-bot" || echo "  PM2 nexus-bot: not running"
    pm2 delete nexus-bot 2>/dev/null || true
    pm2 kill 2>/dev/null && echo "  Killed PM2 daemon" || echo "  PM2 daemon: not running"
else
    echo "  PM2: not installed"
fi
sleep 1

# ── Step 1: Kill ALL bot-related processes ───────────────────────────────────
echo ""
echo "[1/6] Killing all bot processes..."
pkill -9 -f "python.*run\.py" 2>/dev/null && echo "  Killed run.py processes" || echo "  No run.py processes found"
pkill -9 -f "python.*bot\.py" 2>/dev/null && echo "  Killed bot.py processes" || echo "  No bot.py processes found"
sleep 1

# ── Step 2: Verify no ghost processes remain ─────────────────────────────────
echo ""
echo "[2/6] Checking for ghost processes..."
GHOSTS=$(ps aux | grep -E "run\.py|bot\.py" | grep -v grep | grep -v restart.sh || true)
if [ -n "$GHOSTS" ]; then
    echo "  WARNING: Ghost processes found, force killing:"
    echo "$GHOSTS"
    echo "$GHOSTS" | awk '{print $2}' | xargs kill -9 2>/dev/null || true
    sleep 2
    # Final check
    GHOSTS2=$(ps aux | grep -E "run\.py|bot\.py" | grep -v grep | grep -v restart.sh || true)
    if [ -n "$GHOSTS2" ]; then
        echo "  ERROR: Could not kill all processes:"
        echo "$GHOSTS2"
        echo "  Please kill manually and retry."
        exit 1
    fi
fi
echo "  All clear — no bot processes running"

# ── Step 3: Wait for Telegram to release the poll lock ───────────────────────
echo ""
echo "[3/6] Waiting 15s for Telegram to release poll lock..."
sleep 15
echo "  Done waiting"

# ── Step 4: Start the bot ────────────────────────────────────────────────────
echo ""
echo "[4/6] Starting bot..."
cd "$SCRIPT_DIR"
source "$VENV" 2>/dev/null || { echo "  ERROR: venv not found at $VENV"; exit 1; }
nohup python run.py > "$LOG_FILE" 2>&1 &
BOT_PID=$!
echo "  Started with PID $BOT_PID"

# ── Step 5: Verify startup ──────────────────────────────────────────────────
echo ""
echo "[5/6] Verifying startup (waiting 5s)..."
sleep 5

if ps -p $BOT_PID > /dev/null 2>&1; then
    echo "  Bot is running (PID $BOT_PID)"
    # Check for conflict errors
    if grep -q "409 Conflict" "$LOG_FILE" 2>/dev/null; then
        echo "  WARNING: 409 Conflict detected — another instance may still be polling"
        echo "  Check: tail -20 $LOG_FILE"
    elif grep -q "200 OK" "$LOG_FILE" 2>/dev/null; then
        echo "  Telegram connection: OK (200)"
    fi
    # Show config diagnostics
    grep -o "\[config\].*" "$LOG_FILE" 2>/dev/null || true
else
    echo "  ERROR: Bot process died. Check logs:"
    tail -20 "$LOG_FILE"
    exit 1
fi

# ── Step 6: Final status ────────────────────────────────────────────────────
echo ""
echo "[6/6] Final process check..."
ps aux | grep -E "run\.py|bot\.py" | grep -v grep | grep -v restart.sh || echo "  No processes found (unexpected)"
echo ""
echo "=== Restart complete ==="
echo "Logs: tail -f $LOG_FILE"
