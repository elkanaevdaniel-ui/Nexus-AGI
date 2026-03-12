#!/bin/bash
# ================================================================
# NEXUS AGI — AWS EC2 Setup Script (Unified System)
# Run once on a fresh Ubuntu 22.04/24.04 AWS instance
# Usage: sudo bash setup-aws.sh your-domain.duckdns.org
# ================================================================
set -euo pipefail

NEXUS_USER="${SUDO_USER:-ubuntu}"
NEXUS_HOME="/home/$NEXUS_USER"
PROJECT_ROOT="$NEXUS_HOME/ai-projects"
PROJECT_DIR="$PROJECT_ROOT/workdir"
DOMAIN="${1:-nexus-elkana.duckdns.org}"
VENV_DIR="$NEXUS_HOME/nexus-venv"
ENV_FILE="$PROJECT_ROOT/.env"

echo "================================================"
echo "  NEXUS AGI — Unified System AWS Setup"
echo "  User: $NEXUS_USER"
echo "  Domain: $DOMAIN"
echo "================================================"

# ── 1. System updates ────────────────────────────────────────────
echo "[1/12] Updating system..."
apt-get update -qq && apt-get upgrade -y -qq

# ── 2. Install system dependencies ───────────────────────────────
echo "[2/12] Installing system dependencies..."
apt-get install -y -qq \
    python3 python3-pip python3-venv \
    git curl wget sqlite3 htop \
    redis-server \
    debian-keyring debian-archive-keyring apt-transport-https \
    ffmpeg fail2ban ufw unattended-upgrades

# ── 3. Install Node.js & pnpm (for Next.js frontend) ────────────
echo "[3/12] Installing Node.js & pnpm..."
if ! command -v node &>/dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y -qq nodejs
fi
if ! command -v pnpm &>/dev/null; then
    npm install -g pnpm
fi

# ── 4. Install Caddy ────────────────────────────────────────────
echo "[4/12] Installing Caddy..."
if ! command -v caddy &>/dev/null; then
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
    apt-get update -qq && apt-get install -y -qq caddy
fi

# ── 5. Configure Caddy ──────────────────────────────────────────
echo "[5/12] Configuring Caddy reverse proxy..."
mkdir -p /var/log/caddy
sed "s|__DOMAIN__|$DOMAIN|g" "$PROJECT_DIR/cloud/Caddyfile" > /etc/caddy/Caddyfile
systemctl enable caddy
systemctl restart caddy

# ── 6. Configure Firewall (UFW) ─────────────────────────────────
echo "[6/12] Configuring firewall..."
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP (Let's Encrypt)
ufw allow 443/tcp   # HTTPS
ufw --force enable

# ── 7. Configure fail2ban ───────────────────────────────────────
echo "[7/12] Configuring fail2ban..."
cat > /etc/fail2ban/jail.local <<'FAIL2BAN'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5
backend = systemd

[sshd]
enabled = true
port = ssh
maxretry = 3
bantime = 7200
FAIL2BAN
systemctl enable fail2ban
systemctl restart fail2ban

# ── 8. Harden SSH ───────────────────────────────────────────────
echo "[8/12] Hardening SSH..."
sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/#PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
systemctl restart sshd

# ── 9. Configure Redis (bind localhost, require password) ───────
echo "[9/12] Securing Redis..."
REDIS_PASS=$(openssl rand -hex 16)
sed -i "s/^# requirepass .*/requirepass $REDIS_PASS/" /etc/redis/redis.conf
sed -i "s/^bind .*/bind 127.0.0.1 ::1/" /etc/redis/redis.conf
systemctl enable redis-server
systemctl restart redis-server
# Update .env with Redis password
if [ -f "$ENV_FILE" ]; then
    sed -i "s|^REDIS_URL=.*|REDIS_URL=redis://:$REDIS_PASS@localhost:6379/0|" "$ENV_FILE"
fi

# ── 10. Create Python virtual environment ────────────────────────
echo "[10/12] Setting up Python venv & installing dependencies..."
sudo -u "$NEXUS_USER" python3 -m venv "$VENV_DIR"
sudo -u "$NEXUS_USER" "$VENV_DIR/bin/pip" install --upgrade pip
sudo -u "$NEXUS_USER" "$VENV_DIR/bin/pip" install -r "$PROJECT_ROOT/requirements.txt"

# ── 11. Build Next.js frontend ──────────────────────────────────
echo "[11/12] Building Next.js frontend..."
FRONTEND_DIR="$PROJECT_DIR/nexus-agi/command-center/frontend"
if [ -d "$FRONTEND_DIR" ]; then
    cd "$FRONTEND_DIR"
    sudo -u "$NEXUS_USER" pnpm install --frozen-lockfile 2>/dev/null || sudo -u "$NEXUS_USER" pnpm install
    sudo -u "$NEXUS_USER" pnpm build
    cd -
fi

# ── 12. Create directories & install services ────────────────────
echo "[12/12] Installing systemd services..."
sudo -u "$NEXUS_USER" mkdir -p "$PROJECT_DIR/linkedin-bot/data"
sudo -u "$NEXUS_USER" mkdir -p "$PROJECT_DIR/linkedin-bot/logs"
sudo -u "$NEXUS_USER" mkdir -p "$PROJECT_DIR/linkedin-bot/output"
sudo -u "$NEXUS_USER" mkdir -p "$PROJECT_DIR/nexus-agi/data"
sudo -u "$NEXUS_USER" mkdir -p "$PROJECT_DIR/nexus-agi/data/backups"

CLOUD_DIR="$PROJECT_DIR/cloud"

# Copy service files
for svc in nexus-api nexus-frontend nexus-bot nexus-worker nexus-sigma nexus-dashboard nexus-backup; do
    if [ -f "$CLOUD_DIR/services/${svc}.service" ]; then
        cp "$CLOUD_DIR/services/${svc}.service" /etc/systemd/system/
    fi
done
if [ -f "$CLOUD_DIR/services/nexus-backup.timer" ]; then
    cp "$CLOUD_DIR/services/nexus-backup.timer" /etc/systemd/system/
fi

# Detect pnpm path
PNPM_BIN=$(command -v pnpm 2>/dev/null || echo "/usr/local/bin/pnpm")

# Replace placeholders
sed -i "s|__NEXUS_USER__|$NEXUS_USER|g" /etc/systemd/system/nexus-*.service 2>/dev/null || true
sed -i "s|__NEXUS_HOME__|$NEXUS_HOME|g" /etc/systemd/system/nexus-*.service 2>/dev/null || true
sed -i "s|__PROJECT_DIR__|$PROJECT_DIR|g" /etc/systemd/system/nexus-*.service 2>/dev/null || true
sed -i "s|__VENV_DIR__|$VENV_DIR|g" /etc/systemd/system/nexus-*.service 2>/dev/null || true
sed -i "s|__ENV_FILE__|$ENV_FILE|g" /etc/systemd/system/nexus-*.service 2>/dev/null || true
sed -i "s|__PNPM_BIN__|$PNPM_BIN|g" /etc/systemd/system/nexus-*.service 2>/dev/null || true

# Secure .env
if [ -f "$ENV_FILE" ]; then
    chmod 600 "$ENV_FILE"
    chown "$NEXUS_USER:$NEXUS_USER" "$ENV_FILE"
fi

# Enable and start core services
systemctl daemon-reload
systemctl enable nexus-api nexus-frontend nexus-bot nexus-worker nexus-backup.timer redis-server caddy
systemctl start nexus-api nexus-frontend nexus-bot nexus-worker nexus-backup.timer

# Enable auto-updates
dpkg-reconfigure -plow unattended-upgrades 2>/dev/null || true

# ── Setup swap (AWS free tier has limited RAM) ───────────────────
echo "[+] Setting up 2GB swap file..."
if [ ! -f /swapfile ]; then
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    sysctl vm.swappiness=10
    echo 'vm.swappiness=10' >> /etc/sysctl.conf
fi

echo ""
echo "================================================"
echo "  NEXUS AGI — Unified System Setup Complete!"
echo "================================================"
echo ""
echo "  Core Services:"
echo "    - nexus-api        (Command Center API :8080)"
echo "    - nexus-frontend   (Next.js Dashboard :3000)"
echo "    - nexus-bot        (Telegram Bot - Herald)"
echo "    - nexus-worker     (arq Background Worker)"
echo "    - redis-server     (Cache & Message Broker)"
echo "    - caddy            (HTTPS Reverse Proxy)"
echo ""
echo "  Optional Services (enable manually):"
echo "    - nexus-sigma      (Trading Terminal :8501)"
echo "    - nexus-dashboard  (LinkedIn Bot Dashboard :7860)"
echo ""
echo "  Security:"
echo "    - UFW firewall: ports 22, 80, 443 only"
echo "    - fail2ban: SSH brute-force protection"
echo "    - SSH: key-only auth, root login disabled"
echo "    - Redis: localhost-only, password protected"
echo "    - Caddy: auto-HTTPS with HSTS"
echo "    - Auto security updates enabled"
echo ""
echo "  Your site: https://$DOMAIN"
echo ""
echo "  IMPORTANT: Edit your .env file first!"
echo "    nano $ENV_FILE"
echo "================================================"
