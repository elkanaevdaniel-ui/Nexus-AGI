#!/bin/bash
# ================================================================
# NEXUS AGI System — Full Startup Script
# Starts all 7 services + tunnels in correct order
# ================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BOT_DIR="$SCRIPT_DIR"
WORKDIR="$(cd "$BOT_DIR/.." && pwd)"
NEXUS_DIR="$WORKDIR/nexus-agi"
TUNNEL_KEY="$NEXUS_DIR/infrastructure/nexus_tunnel_key"

cd "$BOT_DIR"

echo "================================================"
echo "  NEXUS AGI System — Starting Up"
echo "================================================"

# ─── Phase 1: Stop existing processes ──────────────────────────────────
echo ""
echo "[1/7] Stopping old processes..."
pkill -f 'python3 run.py' 2>/dev/null || true
pkill -f 'dashboard/app.py' 2>/dev/null || true
pkill -f 'watchdog.py' 2>/dev/null || true
pkill -f 'jarvis_pwa_server.py' 2>/dev/null || true
pkill -f 'nexus_dashboard_server.py' 2>/dev/null || true
pkill -f 'jarvis_phone_server.py' 2>/dev/null || true
pkill -f 'nokey@localhost.run' 2>/dev/null || true
pkill -f 'localhost.run' 2>/dev/null || true
sleep 2

# ─── Phase 2: Prepare logs ────────────────────────────────────────────
mkdir -p logs
> logs/bot.log
> logs/dashboard.log
> logs/watchdog.log
> logs/tunnel.log
> logs/tunnel_url.txt
> logs/jarvis_pwa.log
> logs/jarvis_phone.log
> logs/nexus_dashboard.log
> logs/tunnel_jarvis.log
> logs/tunnel_nexus_dashboard.log

# ─── Phase 3: Start HERALD Bot ────────────────────────────────────────
echo "[2/7] Starting HERALD bot..."
nohup python3 run.py > logs/bot.log 2>&1 &
echo $! > /tmp/linkedin_bot.pid
echo "  Bot PID: $!"

# ─── Phase 4: Start Watchdog ──────────────────────────────────────────
nohup python3 watchdog.py > logs/watchdog.log 2>&1 &
echo $! > /tmp/linkedin_watchdog.pid
echo "  Watchdog PID: $!"

# ─── Phase 5: Start LinkedIn Dashboard (port 7860) ────────────────────
echo "[3/7] Starting LinkedIn Dashboard (port 7860)..."
nohup python3 dashboard/app.py > logs/dashboard.log 2>&1 &
echo $! > /tmp/linkedin_dashboard.pid
echo "  Dashboard PID: $!"
sleep 2

# ─── Phase 6: Start JARVIS PWA (port 7861) ────────────────────────────
echo "[4/7] Starting JARVIS v0.2 PWA (port 7861)..."
nohup python3 "$NEXUS_DIR/interfaces/jarvis-pwa/jarvis_pwa_server.py" \
    > logs/jarvis_pwa.log 2>&1 &
echo $! > /tmp/jarvis_pwa.pid
echo "  JARVIS PWA PID: $!"
sleep 2

# ─── Phase 7: Start NEXUS Master Dashboard (port 7862) ────────────────
echo "[5/7] Starting NEXUS Master Dashboard (port 7862)..."
nohup python3 "$NEXUS_DIR/interfaces/dashboard/nexus_dashboard_server.py" \
    > logs/nexus_dashboard.log 2>&1 &
echo $! > /tmp/nexus_dashboard.pid
echo "  NEXUS Dashboard PID: $!"
sleep 2

# ─── Phase 8: Start JARVIS Phone (port 7863) ──────────────────────────
echo "[6/7] Starting JARVIS Phone Interface (port 7863)..."
nohup python3 "$NEXUS_DIR/interfaces/jarvis-phone/jarvis_phone_server.py" \
    > logs/jarvis_phone.log 2>&1 &
echo $! > /tmp/jarvis_phone.pid
echo "  JARVIS Phone PID: $!"

# ─── Phase 9: Start SSH Tunnels ───────────────────────────────────────
echo "[7/7] Starting SSH tunnels..."

if [ -f "$TUNNEL_KEY" ]; then
    # Tunnel 1: Dashboard (7860)
    nohup ssh -o StrictHostKeyChecking=no \
             -o ServerAliveInterval=30 \
             -o ServerAliveCountMax=3 \
             -o ExitOnForwardFailure=no \
             -i "$TUNNEL_KEY" \
             -R 80:localhost:7860 \
             nokey@localhost.run > logs/tunnel.log 2>&1 &
    echo $! > /tmp/linkedin_tunnel.pid
    echo "  Dashboard Tunnel PID: $!"

    # Tunnel 2: JARVIS PWA (7861)
    nohup ssh -o StrictHostKeyChecking=no \
             -o ServerAliveInterval=30 \
             -o ServerAliveCountMax=3 \
             -o ExitOnForwardFailure=no \
             -i "$TUNNEL_KEY" \
             -R 80:localhost:7861 \
             nokey@localhost.run > logs/tunnel_jarvis.log 2>&1 &
    echo $! > /tmp/jarvis_tunnel.pid
    echo "  JARVIS Tunnel PID: $!"

    # Tunnel 3: NEXUS Dashboard (7862)
    nohup ssh -o StrictHostKeyChecking=no \
             -o ServerAliveInterval=30 \
             -o ServerAliveCountMax=3 \
             -o ExitOnForwardFailure=no \
             -i "$TUNNEL_KEY" \
             -R 80:localhost:7862 \
             nokey@localhost.run > logs/tunnel_nexus_dashboard.log 2>&1 &
    echo $! > /tmp/nexus_dashboard_tunnel.pid
    echo "  NEXUS Dashboard Tunnel PID: $!"

    # ── Wait for URLs ─────────────────────────────────────────────────
    echo ""
    echo "  Waiting for tunnel URLs (up to 20s)..."
    sleep 6

    URL=$(grep -o 'https://[a-zA-Z0-9]*.lhr.life' logs/tunnel.log 2>/dev/null | tail -1 || true)
    JARVIS_URL=$(grep -o 'https://[a-zA-Z0-9]*.lhr.life' logs/tunnel_jarvis.log 2>/dev/null | tail -1 || true)
    NEXUS_URL=$(grep -o 'https://[a-zA-Z0-9]*.lhr.life' logs/tunnel_nexus_dashboard.log 2>/dev/null | tail -1 || true)

    # Retry if URLs not ready yet
    if [ -z "$URL" ] || [ -z "$JARVIS_URL" ]; then
        sleep 8
        [ -z "$URL" ] && URL=$(grep -o 'https://[a-zA-Z0-9]*.lhr.life' logs/tunnel.log 2>/dev/null | tail -1 || true)
        [ -z "$JARVIS_URL" ] && JARVIS_URL=$(grep -o 'https://[a-zA-Z0-9]*.lhr.life' logs/tunnel_jarvis.log 2>/dev/null | tail -1 || true)
        [ -z "$NEXUS_URL" ] && NEXUS_URL=$(grep -o 'https://[a-zA-Z0-9]*.lhr.life' logs/tunnel_nexus_dashboard.log 2>/dev/null | tail -1 || true)
    fi

    # Save URLs
    [ -n "$URL" ] && echo "$URL" > logs/tunnel_url.txt
    [ -n "$JARVIS_URL" ] && echo "$JARVIS_URL" > logs/tunnel_jarvis_url.txt
    [ -n "$NEXUS_URL" ] && echo "$NEXUS_URL" > logs/tunnel_nexus_url.txt
else
    echo "  WARNING: Tunnel key not found at $TUNNEL_KEY"
    echo "  Tunnels NOT started. Services available on localhost only."
fi

# ─── Phase 10: Status Report ─────────────────────────────────────────
echo ""
echo "================================================"
echo "  NEXUS AGI System Status"
echo "================================================"
echo ""
echo "  Services:"
echo "    HERALD Bot        : PID $(cat /tmp/linkedin_bot.pid 2>/dev/null || echo 'N/A')"
echo "    Watchdog          : PID $(cat /tmp/linkedin_watchdog.pid 2>/dev/null || echo 'N/A')"
echo "    Dashboard  :7860  : PID $(cat /tmp/linkedin_dashboard.pid 2>/dev/null || echo 'N/A')"
echo "    JARVIS PWA :7861  : PID $(cat /tmp/jarvis_pwa.pid 2>/dev/null || echo 'N/A')"
echo "    NEXUS Dash :7862  : PID $(cat /tmp/nexus_dashboard.pid 2>/dev/null || echo 'N/A')"
echo "    JARVIS Phone:7863 : PID $(cat /tmp/jarvis_phone.pid 2>/dev/null || echo 'N/A')"
echo ""
echo "  URLs:"
echo "    Dashboard (HERALD) : ${URL:-http://localhost:7860}"
echo "    JARVIS PWA         : ${JARVIS_URL:-http://localhost:7861}"
echo "    NEXUS Dashboard    : ${NEXUS_URL:-http://localhost:7862}"
echo "    JARVIS Phone       : http://localhost:7863"
echo ""
echo "  JARVIS PIN: 2026NEXUS"
echo ""
echo "  Logs:"
echo "    tail -f logs/bot.log"
echo "    tail -f logs/dashboard.log"
echo "    tail -f logs/jarvis_pwa.log"
echo "    tail -f logs/jarvis_phone.log"
echo "    tail -f logs/nexus_dashboard.log"
echo ""
echo "  Commands:"
echo "    Get URLs : bash get_url.sh"
echo "    Stop all : bash stop_all.sh"
echo "================================================"
