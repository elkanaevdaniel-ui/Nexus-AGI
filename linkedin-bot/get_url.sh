#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "================================================"
echo "  LinkedIn Bot - Dashboard Access Info"
echo "================================================"

# Check if tunnel process is alive
TUNNEL_PID=$(cat /tmp/linkedin_tunnel.pid 2>/dev/null)
if [ -n "$TUNNEL_PID" ] && kill -0 "$TUNNEL_PID" 2>/dev/null; then
    TUNNEL_STATUS="✅ Running (PID: $TUNNEL_PID)"
else
    TUNNEL_STATUS="❌ Not running"
fi

# Get current URL from log
URL=$(grep -o 'https://[a-zA-Z0-9]*.lhr.life' logs/tunnel.log 2>/dev/null | tail -1)
SAVED_URL=$(cat logs/tunnel_url.txt 2>/dev/null)

echo ""
echo "  Tunnel   : $TUNNEL_STATUS"
echo "  Live URL : ${URL:-Not found - run launch_all.sh}"
echo ""

# Check bot process
BOT_PID=$(cat /tmp/linkedin_bot.pid 2>/dev/null)
if [ -n "$BOT_PID" ] && kill -0 "$BOT_PID" 2>/dev/null; then
    echo "  Bot      : ✅ Running (PID: $BOT_PID)"
else
    echo "  Bot      : ❌ Not running"
fi

# Check dashboard process
DASH_PID=$(cat /tmp/linkedin_dashboard.pid 2>/dev/null)
if [ -n "$DASH_PID" ] && kill -0 "$DASH_PID" 2>/dev/null; then
    echo "  Dashboard: ✅ Running (PID: $DASH_PID)"
else
    echo "  Dashboard: ❌ Not running"
fi

echo ""
if [ -n "$URL" ]; then
    echo "  👉 Open this in your browser:"
    echo "     $URL"
fi
echo "================================================"
