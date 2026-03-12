#!/usr/bin/env bash
# ==============================================================================
# watchlist_monitor.sh — Monitor watched markets and trigger alerts
# ==============================================================================
# Run periodically via cron or Agent Zero:
#   bash ~/polymarket-agent/scripts/watchlist_monitor.sh
#
# Checks each active watchlist item for price moves, triggers UI + webhook alerts
# ==============================================================================

set -e

DB_PATH="$HOME/polymarket-agent/data/a0_memory.db"
TOKEN_FILE="$HOME/.polymarket-token"
API_BASE="http://localhost:8000"
LOG_FILE="$HOME/polymarket-agent/data/watchlist_alerts.log"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"; }

# Check dependencies
if [ ! -f "$DB_PATH" ]; then
    echo "Error: Memory DB not found at $DB_PATH. Run setup_a0_memory.sh first."
    exit 1
fi

if [ ! -f "$TOKEN_FILE" ]; then
    echo "Warning: Token file not found. Some API calls may fail."
fi

AUTH_HEADER=""
if [ -f "$TOKEN_FILE" ]; then
    AUTH_HEADER="Authorization: Bearer $(cat "$TOKEN_FILE")"
fi

log "=== Watchlist Monitor Starting ==="

# Get active watchlist items
WATCHLIST=$(sqlite3 -json "$DB_PATH" "SELECT id, market_id, market_question, current_price, our_estimate, alert_threshold, alert_type, webhook_url FROM watchlist WHERE active=1;" 2>/dev/null)

if [ -z "$WATCHLIST" ] || [ "$WATCHLIST" = "[]" ]; then
    log "No active watchlist items."
    exit 0
fi

ALERT_COUNT=0

# Process each watchlist item
echo "$WATCHLIST" | python3 -c "
import json, sys, subprocess, urllib.request, os
from datetime import datetime

items = json.load(sys.stdin)
db_path = os.environ.get('DB_PATH', '$DB_PATH')
api_base = '$API_BASE'

for item in items:
    market_id = item['market_id']
    old_price = item.get('current_price', 0)
    threshold = item.get('alert_threshold', 0.05)
    alert_type = item.get('alert_type', 'price_move')
    webhook_url = item.get('webhook_url', '')
    question = item.get('market_question', 'Unknown')

    # Fetch current market data from API
    try:
        url = f'{api_base}/api/markets/{market_id}'
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            market_data = json.loads(resp.read())
            new_price = float(market_data.get('yes_price', market_data.get('price', 0)))
    except Exception as e:
        print(f'  SKIP {market_id}: API error: {e}')
        continue

    # Calculate price change
    if old_price and old_price > 0:
        change = abs(new_price - old_price)
        change_pct = change / old_price
    else:
        change = 0
        change_pct = 0

    # Update current price in DB
    subprocess.run([
        'sqlite3', db_path,
        f\"UPDATE watchlist SET current_price={new_price}, last_checked=datetime('now') WHERE market_id='{market_id}';\"
    ], capture_output=True)

    # Check if alert should fire
    should_alert = False
    alert_msg = ''

    if alert_type == 'price_move' and change_pct >= threshold:
        direction = '📈' if new_price > old_price else '📉'
        alert_msg = f'{direction} PRICE ALERT: {question}\nWas: {old_price:.2f} → Now: {new_price:.2f} (change: {change_pct:.1%})'
        should_alert = True

    elif alert_type == 'resolution' and new_price >= 0.95:
        alert_msg = f'🏁 RESOLUTION ALERT: {question}\nPrice at {new_price:.2f} — likely resolving soon'
        should_alert = True

    elif alert_type == 'volume_spike':
        # Would need volume data from API
        pass

    if should_alert:
        print(f'  🔔 ALERT: {alert_msg}')

        # Update last alert time
        subprocess.run([
            'sqlite3', db_path,
            f\"UPDATE watchlist SET last_alert_at=datetime('now') WHERE market_id='{market_id}';\"
        ], capture_output=True)

        # Send webhook if configured
        if webhook_url:
            try:
                payload = json.dumps({
                    'text': alert_msg,
                    'market_id': market_id,
                    'old_price': old_price,
                    'new_price': new_price,
                    'change_pct': change_pct,
                    'timestamp': datetime.now().isoformat()
                }).encode()
                req = urllib.request.Request(
                    webhook_url,
                    data=payload,
                    headers={'Content-Type': 'application/json'},
                    method='POST'
                )
                urllib.request.urlopen(req, timeout=10)
                print(f'  ✅ Webhook sent to {webhook_url[:50]}...')
            except Exception as e:
                print(f'  ❌ Webhook failed: {e}')

        # Store alert in Redis for UI display
        try:
            subprocess.run([
                'redis-cli', 'LPUSH', 'a0:alerts',
                json.dumps({'msg': alert_msg, 'time': datetime.now().isoformat(), 'market_id': market_id})
            ], capture_output=True, timeout=5)
            subprocess.run(['redis-cli', 'LTRIM', 'a0:alerts', '0', '49'], capture_output=True, timeout=5)
        except Exception:
            pass
    else:
        print(f'  ✓ {question[:60]}... price={new_price:.2f} (no alert)')
" 2>&1

log "=== Watchlist Monitor Complete ==="
