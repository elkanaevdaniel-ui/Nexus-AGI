#!/bin/bash
# ================================================================
# NEXUS AGI — Universal Cloud Deploy Script
# Works on any Ubuntu 22.04/24.04 VPS (AWS, Hetzner, Oracle, etc.)
#
# Usage:
#   sudo bash deploy.sh <domain> [--docker]
#
# Examples:
#   sudo bash deploy.sh nexus-elkana.duckdns.org          # systemd mode
#   sudo bash deploy.sh nexus-elkana.duckdns.org --docker  # Docker mode
# ================================================================
set -euo pipefail

NEXUS_USER="${SUDO_USER:-ubuntu}"
NEXUS_HOME="/home/$NEXUS_USER"
PROJECT_DIR="$NEXUS_HOME/ai-projects/workdir"
DOMAIN="${1:-nexus-elkana.duckdns.org}"
MODE="systemd"

# Parse flags
for arg in "$@"; do
    case $arg in
        --docker) MODE="docker" ;;
    esac
done

echo "================================================"
echo "  NEXUS AGI — Universal Cloud Deploy"
echo "  User:   $NEXUS_USER"
echo "  Domain: $DOMAIN"
echo "  Mode:   $MODE"
echo "================================================"

# ── 1. System updates ────────────────────────────────────────────
echo "[1/9] Updating system..."
apt-get update -qq && apt-get upgrade -y -qq

# ── 2. Install core dependencies ─────────────────────────────────
echo "[2/9] Installing system dependencies..."
apt-get install -y -qq \
    python3 python3-pip python3-venv \
    git curl wget sqlite3 htop \
    redis-server \
    ffmpeg \
    debian-keyring debian-archive-keyring apt-transport-https

# ── 3. Install Caddy (HTTPS reverse proxy) ───────────────────────
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
    # NEXUS Command Center (main landing page)
    handle / {
        reverse_proxy localhost:7862
    }
    handle /api/nexus/* {
        reverse_proxy localhost:7862
    }
    handle /static/* {
        reverse_proxy localhost:7862
    }
    handle /health {
        reverse_proxy localhost:7862
    }

    # LinkedIn Dashboard
    handle /dashboard/* {
        reverse_proxy localhost:7860
    }
    handle /api/* {
        reverse_proxy localhost:7860
    }

    # JARVIS PWA
    handle /jarvis/* {
        reverse_proxy localhost:7861
    }

    # JARVIS Phone (Twilio webhook)
    handle /voice/* {
        reverse_proxy localhost:7863
    }

    # Default → Command Center
    handle {
        reverse_proxy localhost:7862
    }

    header {
        X-Frame-Options DENY
        X-Content-Type-Options nosniff
        Referrer-Policy strict-origin-when-cross-origin
    }
}
CADDYEOF
systemctl enable caddy
systemctl restart caddy

# ── 5. Firewall ──────────────────────────────────────────────────
echo "[5/9] Configuring firewall..."
if command -v ufw &>/dev/null; then
    ufw allow 22/tcp
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw --force enable
else
    iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT 2>/dev/null || true
    iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT 2>/dev/null || true
    apt-get install -y -qq netfilter-persistent
    netfilter-persistent save 2>/dev/null || true
fi

# ── 6. Enable Redis ──────────────────────────────────────────────
echo "[6/9] Starting Redis..."
systemctl enable redis-server
systemctl start redis-server

# ── 7. Clone repo if not already present ─────────────────────────
echo "[7/9] Setting up project..."
if [ ! -d "$NEXUS_HOME/ai-projects" ]; then
    sudo -u "$NEXUS_USER" git clone https://github.com/elkanaevdaniel-ui/ai-projects.git "$NEXUS_HOME/ai-projects"
else
    cd "$NEXUS_HOME/ai-projects"
    sudo -u "$NEXUS_USER" git pull origin main || true
fi

# Create data directories
sudo -u "$NEXUS_USER" mkdir -p "$PROJECT_DIR/linkedin-bot/data"
sudo -u "$NEXUS_USER" mkdir -p "$PROJECT_DIR/linkedin-bot/logs"
sudo -u "$NEXUS_USER" mkdir -p "$PROJECT_DIR/linkedin-bot/output"
sudo -u "$NEXUS_USER" mkdir -p "$PROJECT_DIR/cost-optimizer/data"
sudo -u "$NEXUS_USER" mkdir -p "$PROJECT_DIR/nexus-agi/data"

# ── 8. Setup swap (for low-memory VPS) ────────────────────────────
echo "[8/9] Setting up swap..."
if [ ! -f /swapfile ]; then
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    sysctl vm.swappiness=10
    echo 'vm.swappiness=10' >> /etc/sysctl.conf
fi

# ── 9. Deploy services ───────────────────────────────────────────
echo "[9/9] Deploying services ($MODE mode)..."

if [ "$MODE" = "docker" ]; then
    # ── Docker Mode ──────────────────────────────────────────────
    if ! command -v docker &>/dev/null; then
        curl -fsSL https://get.docker.com | sh
        usermod -aG docker "$NEXUS_USER"
    fi

    cd "$PROJECT_DIR/configs"
    docker compose -f docker-compose.prod.yml down 2>/dev/null || true
    docker compose -f docker-compose.prod.yml build
    docker compose -f docker-compose.prod.yml up -d

    echo ""
    echo "  Docker containers:"
    docker compose -f docker-compose.prod.yml ps
else
    # ── Systemd Mode ─────────────────────────────────────────────
    VENV_DIR="$NEXUS_HOME/nexus-venv"

    # Create virtual environment
    if [ ! -d "$VENV_DIR" ]; then
        sudo -u "$NEXUS_USER" python3 -m venv "$VENV_DIR"
    fi
    sudo -u "$NEXUS_USER" "$VENV_DIR/bin/pip" install --upgrade pip -q
    sudo -u "$NEXUS_USER" "$VENV_DIR/bin/pip" install -r "$PROJECT_DIR/linkedin-bot/requirements.txt" -q

    # Copy all service files
    CLOUD_DIR="$PROJECT_DIR/cloud"
    for svc in nexus-bot nexus-dashboard nexus-command nexus-jarvis-pwa nexus-jarvis-phone nexus-backup; do
        if [ -f "$CLOUD_DIR/services/$svc.service" ]; then
            cp "$CLOUD_DIR/services/$svc.service" /etc/systemd/system/
        fi
    done
    cp "$CLOUD_DIR/services/nexus-backup.timer" /etc/systemd/system/

    # Replace placeholders
    sed -i "s|__NEXUS_USER__|$NEXUS_USER|g" /etc/systemd/system/nexus-*.service
    sed -i "s|__NEXUS_HOME__|$NEXUS_HOME|g" /etc/systemd/system/nexus-*.service
    sed -i "s|__PROJECT_DIR__|$PROJECT_DIR|g" /etc/systemd/system/nexus-*.service
    sed -i "s|__VENV_DIR__|$VENV_DIR|g" /etc/systemd/system/nexus-*.service

    # Enable and start all services
    systemctl daemon-reload
    SERVICES="nexus-bot nexus-dashboard nexus-command nexus-jarvis-pwa nexus-jarvis-phone nexus-backup.timer"
    systemctl enable $SERVICES
    systemctl start $SERVICES

    # Verify
    sleep 3
    echo ""
    echo "  Service Status:"
    for svc in nexus-bot nexus-dashboard nexus-command nexus-jarvis-pwa nexus-jarvis-phone; do
        status=$(systemctl is-active $svc 2>/dev/null || echo "inactive")
        printf "    %-25s %s\n" "$svc" "$status"
    done
fi

echo ""
echo "================================================"
echo "  NEXUS AGI — Deploy Complete!"
echo "================================================"
echo ""
echo "  Mode: $MODE"
echo "  Site: https://$DOMAIN"
echo ""
echo "  Services:"
echo "    :7860  LinkedIn Dashboard"
echo "    :7861  JARVIS Voice PWA"
echo "    :7862  NEXUS Command Center"
echo "    :7863  JARVIS Phone (Twilio)"
echo "    Bot    Telegram Bot"
echo ""
echo "  Quick commands:"
if [ "$MODE" = "docker" ]; then
    echo "    docker compose -f $PROJECT_DIR/configs/docker-compose.prod.yml ps"
    echo "    docker compose -f $PROJECT_DIR/configs/docker-compose.prod.yml logs -f herald-bot"
    echo "    docker compose -f $PROJECT_DIR/configs/docker-compose.prod.yml restart"
else
    echo "    sudo systemctl status nexus-bot"
    echo "    sudo journalctl -u nexus-bot -f"
    echo "    sudo systemctl restart nexus-bot"
fi
echo ""
echo "  IMPORTANT: Create your .env file first!"
echo "    cp $PROJECT_DIR/linkedin-bot/.env.example $PROJECT_DIR/linkedin-bot/.env"
echo "    nano $PROJECT_DIR/linkedin-bot/.env"
echo "================================================"
