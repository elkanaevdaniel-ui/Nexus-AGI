#!/bin/bash
# ================================================================
# Deploy Lead Gen App — Fixes Caddy, rebuilds frontend, restarts all
# Usage: sudo bash deploy-leadgen.sh
# ================================================================
set -e

DOMAIN="nexus-elkana.duckdns.org"
NEXUS_USER="${SUDO_USER:-ubuntu}"
NEXUS_HOME="/home/$NEXUS_USER"
PROJECT_ROOT="$NEXUS_HOME/ai-projects"
PROJECT_DIR="$PROJECT_ROOT/workdir"
FRONTEND_DIR="$PROJECT_DIR/lead-gen/frontend"
PNPM_BIN=$(command -v pnpm 2>/dev/null || echo "/usr/local/bin/pnpm")
ENV_FILE="$PROJECT_ROOT/.env"
VENV_DIR="$NEXUS_HOME/nexus-venv"

echo "================================================"
echo "  Deploying Lead Gen App"
echo "  Domain: $DOMAIN"
echo "  User: $NEXUS_USER"
echo "  pnpm: $PNPM_BIN"
echo "================================================"

# ── 1. Update Caddyfile ──────────────────────────────────────────
echo "[1/6] Updating Caddyfile..."
mkdir -p /var/log/caddy
# Use full Caddyfile from repo (includes all services), replace domain placeholder
CADDY_TEMPLATE="$PROJECT_DIR/cloud/Caddyfile"
if [ -f "$CADDY_TEMPLATE" ]; then
    sed "s/__DOMAIN__/$DOMAIN/g" "$CADDY_TEMPLATE" > /etc/caddy/Caddyfile
    echo "  Used full Caddyfile template from repo"
else
    echo "  WARNING: No Caddyfile template found at $CADDY_TEMPLATE"
    echo "  Keeping existing /etc/caddy/Caddyfile"
fi
echo "  OK"

# ── 2. Set up Python venv if needed ──────────────────────────────
echo "[2/6] Checking Python venv..."
LEAD_GEN_DIR="$PROJECT_DIR/lead-gen"
if [ ! -d "$LEAD_GEN_DIR/.venv" ]; then
    echo "  Creating Python venv..."
    sudo -u "$NEXUS_USER" python3 -m venv "$LEAD_GEN_DIR/.venv"
    sudo -u "$NEXUS_USER" "$LEAD_GEN_DIR/.venv/bin/pip" install -r "$LEAD_GEN_DIR/requirements.txt"
    echo "  Venv created and deps installed"
    VENV_DIR="$LEAD_GEN_DIR/.venv"
else
    echo "  Venv already exists"
    VENV_DIR="$LEAD_GEN_DIR/.venv"
fi

# ── 3. Rebuild Next.js frontend ──────────────────────────────────
echo "[3/6] Rebuilding Next.js frontend (with basePath: /leadgen)..."
cd "$FRONTEND_DIR"
export NEXT_PUBLIC_BASE_PATH="/leadgen"
sudo -u "$NEXUS_USER" -E "$PNPM_BIN" install --frozen-lockfile 2>/dev/null || true
sudo -u "$NEXUS_USER" -E "$PNPM_BIN" build
echo "  Build OK"

# ── 4. Update systemd service files ──────────────────────────────
echo "[4/6] Updating service files..."
# Copy fresh service files from repo
cp "$PROJECT_DIR/cloud/services/nexus-leadgen-api.service" /etc/systemd/system/
cp "$PROJECT_DIR/cloud/services/nexus-leadgen-frontend.service" /etc/systemd/system/

# Replace placeholders
for svc in nexus-leadgen-api nexus-leadgen-frontend; do
    sed -i "s|__NEXUS_USER__|$NEXUS_USER|g" "/etc/systemd/system/${svc}.service"
    sed -i "s|__PROJECT_DIR__|$PROJECT_DIR|g" "/etc/systemd/system/${svc}.service"
    sed -i "s|__VENV_DIR__|$VENV_DIR|g" "/etc/systemd/system/${svc}.service"
    sed -i "s|__PNPM_BIN__|$PNPM_BIN|g" "/etc/systemd/system/${svc}.service"
    sed -i "s|__ENV_FILE__|$ENV_FILE|g" "/etc/systemd/system/${svc}.service"
done
echo "  OK"

# ── 5. Restart everything ────────────────────────────────────────
echo "[5/6] Restarting services..."
systemctl daemon-reload

# Caddy
systemctl stop caddy
rm -rf /var/lib/caddy/.local/share/caddy/locks
systemctl start caddy

# Lead gen services
systemctl restart nexus-leadgen-api 2>/dev/null || systemctl start nexus-leadgen-api
systemctl restart nexus-leadgen-frontend 2>/dev/null || systemctl start nexus-leadgen-frontend
echo "  OK"

# ── 6. Verify ────────────────────────────────────────────────────
echo "[6/6] Verifying (waiting 5s for services to start)..."
sleep 5

echo ""
printf "  %-30s" "Caddy:"
systemctl is-active caddy 2>/dev/null && echo "OK" || echo "FAILED"

printf "  %-30s" "Lead Gen API (port 8082):"
systemctl is-active nexus-leadgen-api 2>/dev/null && echo "OK" || echo "FAILED"

printf "  %-30s" "Lead Gen Frontend (port 3001):"
systemctl is-active nexus-leadgen-frontend 2>/dev/null && echo "OK" || echo "FAILED"

echo ""
echo "  Testing connectivity..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3001/leadgen/ 2>/dev/null || echo "000")
printf "  %-30s HTTP %s\n" "localhost:3001/leadgen/" "$HTTP_CODE"

API_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8082/api/health 2>/dev/null || echo "000")
printf "  %-30s HTTP %s\n" "localhost:8082/api/health" "$API_CODE"

echo ""
echo "================================================"
if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "307" ] || [ "$HTTP_CODE" = "308" ]; then
    echo "  SUCCESS! App is live at:"
    echo "  https://$DOMAIN/leadgen/"
else
    echo "  WARNING: Frontend returned HTTP $HTTP_CODE"
    echo "  Check logs: sudo journalctl -u nexus-leadgen-frontend -n 30"
fi
echo "================================================"
