#!/bin/bash
# ================================================================
# NEXUS AGI — Hetzner Cloud Setup Script (No Docker)
# Run once on a fresh Ubuntu 22.04 Hetzner VPS
# Usage: sudo bash setup-hetzner.sh your-domain.duckdns.org
# ================================================================
set -euo pipefail

NEXUS_USER="${SUDO_USER:-nexus}"
NEXUS_HOME="/home/$NEXUS_USER"
PROJECT_DIR="$NEXUS_HOME/ai-projects/workdir"
DOMAIN="${1:-nexus-agi.duckdns.org}"

echo "================================================"
echo "  NEXUS AGI — Hetzner Cloud Setup"
echo "  User: $NEXUS_USER"
echo "  Domain: $DOMAIN"
echo "================================================"

# ── 1. System updates ────────────────────────────────────────────
echo "[1/9] Updating system..."
apt-get update -qq && apt-get upgrade -y -qq

# ── 2. Install Python 3 & dependencies ───────────────────────────
echo "[2/9] Installing Python & system dependencies..."
apt-get install -y -qq \
    python3 python3-pip python3-venv \
    git curl wget sqlite3 \
    redis-server \
    debian-keyring debian-archive-keyring apt-transport-https \
    ufw htop

# ── 3. Install Caddy ─────────────────────────────────────────────
echo "[3/9] Installing Caddy..."
if ! command -v caddy &>/dev/null; then
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
    apt-get update -qq && apt-get install -y -qq caddy
fi

# ── 4. Configure Caddy ───────────────────────────────────────────
echo "[4/9] Configuring Caddy for $DOMAIN..."
cat > /etc/caddy/Caddyfile <<CADDYEOF
$DOMAIN {
    # NEXUS Command Center
    reverse_proxy /nexus/* localhost:7862
    reverse_proxy /api/nexus/* localhost:7862

    # LinkedIn Dashboard
    reverse_proxy /dashboard/* localhost:7860
    reverse_proxy /api/* localhost:7860

    # Default: LinkedIn Dashboard
    reverse_proxy localhost:7860
}
CADDYEOF
systemctl enable caddy
systemctl restart caddy

# ── 5. Configure Firewall (UFW) ──────────────────────────────────
echo "[5/9] Configuring firewall (UFW)..."
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# ── 6. Enable Redis ──────────────────────────────────────────────
echo "[6/9] Starting Redis..."
systemctl enable redis-server
systemctl start redis-server

# ── 7. Create Python virtual environment ─────────────────────────
echo "[7/9] Setting up Python virtual environment..."
VENV_DIR="$NEXUS_HOME/nexus-venv"
sudo -u "$NEXUS_USER" python3 -m venv "$VENV_DIR"
sudo -u "$NEXUS_USER" "$VENV_DIR/bin/pip" install --upgrade pip
sudo -u "$NEXUS_USER" "$VENV_DIR/bin/pip" install -r "$PROJECT_DIR/linkedin-bot/requirements.txt"

# ── 8. Create data directories ───────────────────────────────────
echo "[8/9] Creating data directories..."
sudo -u "$NEXUS_USER" mkdir -p "$PROJECT_DIR/linkedin-bot/data"
sudo -u "$NEXUS_USER" mkdir -p "$PROJECT_DIR/linkedin-bot/logs"
sudo -u "$NEXUS_USER" mkdir -p "$PROJECT_DIR/linkedin-bot/output"
sudo -u "$NEXUS_USER" mkdir -p "$PROJECT_DIR/cost-optimizer/data"

# ── 9. Install systemd services ──────────────────────────────────
echo "[9/9] Installing systemd services..."
CLOUD_DIR="$PROJECT_DIR/cloud"

# Copy service files
cp "$CLOUD_DIR/services/nexus-bot.service" /etc/systemd/system/
cp "$CLOUD_DIR/services/nexus-dashboard.service" /etc/systemd/system/
cp "$CLOUD_DIR/services/nexus-command.service" /etc/systemd/system/
cp "$CLOUD_DIR/services/nexus-backup.service" /etc/systemd/system/
cp "$CLOUD_DIR/services/nexus-backup.timer" /etc/systemd/system/

# Replace placeholders in service files
sed -i "s|__NEXUS_USER__|$NEXUS_USER|g" /etc/systemd/system/nexus-*.service
sed -i "s|__NEXUS_HOME__|$NEXUS_HOME|g" /etc/systemd/system/nexus-*.service
sed -i "s|__PROJECT_DIR__|$PROJECT_DIR|g" /etc/systemd/system/nexus-*.service
sed -i "s|__VENV_DIR__|$VENV_DIR|g" /etc/systemd/system/nexus-*.service

# Enable and start services
systemctl daemon-reload
systemctl enable nexus-bot nexus-dashboard nexus-command nexus-backup.timer
systemctl start nexus-bot nexus-dashboard nexus-command nexus-backup.timer

echo ""
echo "================================================"
echo "  NEXUS AGI — Setup Complete! (Hetzner)"
echo "================================================"
echo ""
echo "  Server: Hetzner CX22 (2 vCPU, 4GB RAM)"
echo "  Cost:   ~\$4.35/month"
echo ""
echo "  Services running:"
echo "    - nexus-bot       (Telegram Bot)"
echo "    - nexus-dashboard (LinkedIn Dashboard :7860)"
echo "    - nexus-command   (NEXUS Command Center :7862)"
echo "    - nexus-backup    (Daily GitHub backup)"
echo "    - redis-server    (Message broker)"
echo "    - caddy           (HTTPS reverse proxy)"
echo ""
echo "  Your site: https://$DOMAIN"
echo ""
echo "  Manage services:"
echo "    sudo systemctl status nexus-bot"
echo "    sudo systemctl restart nexus-bot"
echo "    sudo journalctl -u nexus-bot -f"
echo ""
echo "  IMPORTANT: Edit your .env file first!"
echo "    nano $PROJECT_DIR/linkedin-bot/.env"
echo "================================================"
