#!/bin/bash
# EMERGENCY: Cancel all orders and pause trading.
# Use when something goes wrong in production.
#
# Requires KILL_SWITCH_TOKEN env var to be set with a valid JWT token.
# Generate one with: python -c "from src.api.auth import create_access_token; print(create_access_token('killswitch', '<your-jwt-secret>', role='operator'))"
set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"
TOKEN="${KILL_SWITCH_TOKEN:?ERROR: KILL_SWITCH_TOKEN env var must be set with a valid JWT operator token}"

echo "!!! KILL SWITCH ACTIVATED !!!"
echo "Cancelling all open orders and pausing trading..."

# 1. Pause trading
curl -s -X POST "$API_URL/api/controls/trading" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"action": "pause", "reason": "kill_switch"}' || true

# 2. Cancel all orders
curl -s -X POST "$API_URL/api/controls/cancel-all" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" || true

echo ""
echo "Kill switch complete."
echo "- Trading: PAUSED"
echo "- Open orders: CANCELLED"
echo ""
echo "Manual review required before resuming."
