#!/usr/bin/env bash
# Health check script — runs every 5 minutes via cron
# Restarts the service if unhealthy, logs all events
set -uo pipefail

APP_DIR="/home/ubuntu/polymarket-agent"
LOG_FILE="${APP_DIR}/logs/health_check.log"
HEALTH_URL="http://localhost:8000/health"
MAX_RETRIES=3
RETRY_DELAY=5

mkdir -p "$(dirname "$LOG_FILE")"

check_health() {
    local response
    response=$(curl -s -m 10 -w "\n%{http_code}" "$HEALTH_URL" 2>/dev/null)
    local http_code
    http_code=$(echo "$response" | tail -1)
    local body
    body=$(echo "$response" | head -1)

    if [[ "$http_code" == "200" ]] && echo "$body" | grep -q '"status":"ok"'; then
        return 0
    fi
    return 1
}

# Try health check with retries
healthy=false
for i in $(seq 1 $MAX_RETRIES); do
    if check_health; then
        healthy=true
        break
    fi
    sleep $RETRY_DELAY
done

if $healthy; then
    # Only log once per hour to avoid spam
    minute=$(date +%M)
    if [[ "$minute" == "00" ]]; then
        echo "[$(date)] Health OK" >> "$LOG_FILE"
    fi
else
    echo "[$(date)] UNHEALTHY — attempting restart..." >> "$LOG_FILE"
    systemctl restart polymarket-agent 2>> "$LOG_FILE"
    sleep 5

    if check_health; then
        echo "[$(date)] Restart successful — service recovered." >> "$LOG_FILE"
    else
        echo "[$(date)] CRITICAL — restart failed! Manual intervention needed." >> "$LOG_FILE"
    fi
fi
