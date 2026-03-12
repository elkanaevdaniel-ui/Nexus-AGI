#!/bin/bash
# ================================================================
# Setup Lead Gen API Keys — auto-configures .env and restarts
# Usage: sudo bash setup-leadgen-keys.sh
# ================================================================
set -e

NEXUS_USER="${SUDO_USER:-ubuntu}"
NEXUS_HOME="/home/$NEXUS_USER"
PROJECT_ROOT="$NEXUS_HOME/ai-projects"
ENV_FILE="$PROJECT_ROOT/.env"
FRONTEND_DIR="$PROJECT_ROOT/lead-gen/frontend"
PNPM_BIN=$(command -v pnpm 2>/dev/null || echo "/usr/local/bin/pnpm")

echo "================================================"
echo "  Lead Gen — API Key Setup"
echo "================================================"

# ── Ensure .env exists ────────────────────────────────────────────
if [ ! -f "$ENV_FILE" ]; then
    echo "Creating .env from .env.example..."
    cp "$PROJECT_ROOT/.env.example" "$ENV_FILE"
    chown "$NEXUS_USER:$NEXUS_USER" "$ENV_FILE"
    chmod 600 "$ENV_FILE"
fi

# ── 1. Generate COMMAND_CENTER_API_KEY if placeholder ─────────────
CURRENT_CC_KEY=$(grep -oP 'COMMAND_CENTER_API_KEY=\K.*' "$ENV_FILE" 2>/dev/null || echo "")
if [ -z "$CURRENT_CC_KEY" ] || [ "$CURRENT_CC_KEY" = "change-me-to-a-long-random-string" ]; then
    NEW_KEY=$(openssl rand -hex 32)
    echo "[1/4] Generating COMMAND_CENTER_API_KEY..."
    if grep -q "COMMAND_CENTER_API_KEY=" "$ENV_FILE"; then
        sed -i "s|COMMAND_CENTER_API_KEY=.*|COMMAND_CENTER_API_KEY=$NEW_KEY|" "$ENV_FILE"
    else
        echo "COMMAND_CENTER_API_KEY=$NEW_KEY" >> "$ENV_FILE"
    fi
    # Also set NEXT_PUBLIC_API_KEY to match
    if grep -q "NEXT_PUBLIC_API_KEY=" "$ENV_FILE"; then
        sed -i "s|NEXT_PUBLIC_API_KEY=.*|NEXT_PUBLIC_API_KEY=$NEW_KEY|" "$ENV_FILE"
    else
        echo "NEXT_PUBLIC_API_KEY=$NEW_KEY" >> "$ENV_FILE"
    fi
    echo "  Generated: ${NEW_KEY:0:8}...${NEW_KEY: -8}"
else
    NEW_KEY="$CURRENT_CC_KEY"
    echo "[1/4] COMMAND_CENTER_API_KEY already set: ${CURRENT_CC_KEY:0:8}..."
    # Ensure NEXT_PUBLIC_API_KEY matches
    if grep -q "NEXT_PUBLIC_API_KEY=" "$ENV_FILE"; then
        sed -i "s|NEXT_PUBLIC_API_KEY=.*|NEXT_PUBLIC_API_KEY=$CURRENT_CC_KEY|" "$ENV_FILE"
    else
        echo "NEXT_PUBLIC_API_KEY=$CURRENT_CC_KEY" >> "$ENV_FILE"
    fi
fi

# ── 2. Check ANTHROPIC_API_KEY ────────────────────────────────────
echo "[2/4] Checking ANTHROPIC_API_KEY..."
ANTHROPIC_KEY=$(grep -oP 'ANTHROPIC_API_KEY=\K.*' "$ENV_FILE" 2>/dev/null || echo "")
if [ -z "$ANTHROPIC_KEY" ] || [[ "$ANTHROPIC_KEY" == *"your-key"* ]] || [[ "$ANTHROPIC_KEY" == *"..."* ]]; then
    echo "  WARNING: ANTHROPIC_API_KEY not set!"
    echo "  Get one at: https://console.anthropic.com/settings/keys"
    echo "  Then run: sudo sed -i 's|ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=sk-ant-YOUR-KEY|' $ENV_FILE"
    echo ""
else
    echo "  OK: ${ANTHROPIC_KEY:0:12}..."
fi

# ── 3. Check APOLLO_API_KEY ───────────────────────────────────────
echo "[3/4] Checking APOLLO_API_KEY..."
APOLLO_KEY=$(grep -oP 'APOLLO_API_KEY=\K.*' "$ENV_FILE" 2>/dev/null || echo "")
if [ -z "$APOLLO_KEY" ] || [[ "$APOLLO_KEY" == *"your-"* ]]; then
    echo "  WARNING: APOLLO_API_KEY not set!"
    echo "  Get a FREE key at: https://app.apollo.io/settings/integrations/api-keys"
    echo "  Then run: sudo sed -i 's|APOLLO_API_KEY=.*|APOLLO_API_KEY=YOUR-KEY|' $ENV_FILE"
    echo ""
else
    echo "  OK: ${APOLLO_KEY:0:12}..."
fi

# ── 4. Rebuild frontend with API key baked in ─────────────────────
echo "[4/4] Rebuilding frontend with API key..."
API_KEY=$(grep -oP 'NEXT_PUBLIC_API_KEY=\K.*' "$ENV_FILE" 2>/dev/null || echo "$NEW_KEY")
cd "$FRONTEND_DIR"
export NEXT_PUBLIC_API_KEY="$API_KEY"
export NEXT_PUBLIC_BASE_PATH="/leadgen"
sudo -u "$NEXUS_USER" -E "$PNPM_BIN" build
echo "  Build OK"

# ── Restart services ──────────────────────────────────────────────
echo ""
echo "Restarting services..."
systemctl daemon-reload
systemctl restart nexus-leadgen-api
systemctl restart nexus-leadgen-frontend
sleep 3

# ── Verify ────────────────────────────────────────────────────────
echo ""
echo "Service status:"
printf "  %-30s" "Lead Gen API:"
systemctl is-active nexus-leadgen-api && echo "OK" || echo "FAILED"
printf "  %-30s" "Lead Gen Frontend:"
systemctl is-active nexus-leadgen-frontend && echo "OK" || echo "FAILED"

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3001/leadgen/ 2>/dev/null || echo "000")
printf "  %-30s HTTP %s\n" "Frontend:" "$HTTP_CODE"

# Test API auth
API_KEY_TEST=$(curl -s -o /dev/null -w "%{http_code}" -H "x-api-key: $API_KEY" http://localhost:8082/api/campaigns 2>/dev/null || echo "000")
printf "  %-30s HTTP %s\n" "API (with key):" "$API_KEY_TEST"

echo ""
echo "================================================"
echo "  Setup complete!"
echo "  URL: https://nexus-elkana.duckdns.org/leadgen/"
echo ""
if [ "$API_KEY_TEST" = "200" ]; then
    echo "  API auth: WORKING"
else
    echo "  API auth: returned $API_KEY_TEST"
    echo "  If 401, check that .env has matching keys"
fi
echo "================================================"
