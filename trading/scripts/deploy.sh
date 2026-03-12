#!/usr/bin/env bash
# ============================================================
# Polymarket Agent — Full EC2 Deployment Script
# Target: Ubuntu 22.04/24.04 on AWS EC2
# Usage:  chmod +x scripts/deploy.sh && sudo bash scripts/deploy.sh
# ============================================================
set -uo pipefail
# Note: we intentionally omit 'set -e' so that a failure in one step
# does not prevent subsequent steps from running. Each critical step
# checks its own exit status.

# ─── Config ──────────────────────────────────────────────────
APP_DIR="/home/ubuntu/polymarket-agent"
APP_USER="ubuntu"
REPO_URL="${REPO_URL:-https://github.com/elkanaevdaniel-ui/polymarket-agent.git}"
BRANCH="${BRANCH:-claude/polymarket-trading-agent-LJYBO}"
NODE_MAJOR=22
PYTHON_VERSION="python3.11"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[DEPLOY]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ─── Pre-flight checks ──────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    err "This script must be run as root (sudo)"
    exit 1
fi

log "Starting Polymarket Agent deployment..."

# ─── 1. System Dependencies ─────────────────────────────────
log "Step 1/13: Installing system packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq \
    software-properties-common curl wget git \
    build-essential libssl-dev libffi-dev \
    nginx redis-server \
    prometheus \
    apt-transport-https

# Python 3.11
if ! command -v python3.11 &>/dev/null; then
    add-apt-repository -y ppa:deadsnakes/ppa
    apt-get update -qq
    apt-get install -y -qq python3.11 python3.11-venv python3.11-dev
fi

# Node.js 22
if ! command -v node &>/dev/null || [[ $(node -v | cut -d. -f1 | tr -d v) -lt 22 ]]; then
    curl -fsSL https://deb.nodesource.com/setup_${NODE_MAJOR}.x | bash -
    apt-get install -y -qq nodejs
fi

log "System packages installed."

# ─── 2. Clone/Update Repository ─────────────────────────────
log "Step 2/13: Setting up repository..."
if [[ -d "${APP_DIR}/.git" ]]; then
    log "Repository exists, pulling latest from ${BRANCH}..."
    cd "$APP_DIR"
    sudo -u "$APP_USER" git fetch origin "$BRANCH"
    sudo -u "$APP_USER" git checkout "$BRANCH" 2>/dev/null || sudo -u "$APP_USER" git checkout -b "$BRANCH" "origin/$BRANCH"
    sudo -u "$APP_USER" git reset --hard "origin/$BRANCH"
else
    log "Cloning repository..."
    sudo -u "$APP_USER" git clone -b "$BRANCH" "$REPO_URL" "$APP_DIR"
    cd "$APP_DIR"
fi

# Ensure nginx (www-data) can traverse /home/ubuntu to reach dashboard/dist
chmod 755 "/home/${APP_USER}"

# ─── 3. Python Virtual Environment ──────────────────────────
log "Step 3/13: Setting up Python environment..."
if [[ ! -d "${APP_DIR}/venv" ]]; then
    sudo -u "$APP_USER" $PYTHON_VERSION -m venv "${APP_DIR}/venv"
fi
sudo -u "$APP_USER" "${APP_DIR}/venv/bin/pip" install --upgrade pip -q
sudo -u "$APP_USER" "${APP_DIR}/venv/bin/pip" install -r "${APP_DIR}/requirements.txt" -q
log "Python dependencies installed."

# ─── 4. Node.js Dependencies ────────────────────────────────
log "Step 4/13: Installing dashboard dependencies..."
cd "${APP_DIR}/dashboard"
sudo -u "$APP_USER" npm install --silent
log "Node dependencies installed."

# ─── 5. Environment Configuration ───────────────────────────
log "Step 5/13: Configuring environment..."
if [[ ! -f "${APP_DIR}/.env" ]]; then
    cp "${APP_DIR}/.env.example" "${APP_DIR}/.env"
    chown "$APP_USER:$APP_USER" "${APP_DIR}/.env"
    chmod 600 "${APP_DIR}/.env"

    # Generate JWT secret
    JWT_SECRET=$(openssl rand -hex 32)
    sed -i "s/^DASHBOARD_JWT_SECRET=.*/DASHBOARD_JWT_SECRET=${JWT_SECRET}/" "${APP_DIR}/.env"

    # Set HOST to 0.0.0.0 for external access
    sed -i "s/^HOST=.*/HOST=0.0.0.0/" "${APP_DIR}/.env"

    # Add BEHIND_PROXY
    if ! grep -q "BEHIND_PROXY" "${APP_DIR}/.env"; then
        echo "BEHIND_PROXY=true" >> "${APP_DIR}/.env"
    else
        sed -i "s/^BEHIND_PROXY=.*/BEHIND_PROXY=true/" "${APP_DIR}/.env"
    fi

    # Get public IP for CORS
    PUBLIC_IP=$(curl -s -m 5 http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo "")
    if [[ -n "$PUBLIC_IP" ]]; then
        sed -i "s|^CORS_ORIGINS=.*|CORS_ORIGINS=http://localhost:3000,http://localhost:8082,http://${PUBLIC_IP},http://${PUBLIC_IP}:3000,http://${PUBLIC_IP}:8000|" "${APP_DIR}/.env"
    fi

    warn "Created .env from template. Edit ${APP_DIR}/.env to add your API keys:"
    warn "  - ANTHROPIC_API_KEY"
    warn "  - OPENAI_API_KEY"
    warn "  - GOOGLE_API_KEY"
    warn "  - POLYMARKET_PRIVATE_KEY (for live trading)"
    warn "  - TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID (for alerts)"
else
    log ".env already exists, preserving existing config."
    # Ensure HOST is set for external access
    if grep -q "^HOST=127.0.0.1" "${APP_DIR}/.env"; then
        sed -i "s/^HOST=127.0.0.1/HOST=0.0.0.0/" "${APP_DIR}/.env"
        log "Updated HOST to 0.0.0.0 for external access."
    fi
fi

# ─── 6. Build React Dashboard ───────────────────────────────
log "Step 6/13: Building React dashboard..."
cd "${APP_DIR}/dashboard"
if sudo -u "$APP_USER" npm run build; then
    log "Dashboard built successfully."
else
    warn "Dashboard build failed — creating minimal redirect page."
    warn "Fix TS errors and rebuild with: cd dashboard && npm run build"
fi

# Ensure dist/index.html always exists (fallback to redirect to /docs)
if [[ ! -f "${APP_DIR}/dashboard/dist/index.html" ]]; then
    mkdir -p "${APP_DIR}/dashboard/dist"
    cat > "${APP_DIR}/dashboard/dist/index.html" << 'FALLBACK'
<!DOCTYPE html>
<html><head><title>Polymarket Agent</title></head>
<body style="font-family:sans-serif;text-align:center;padding:50px">
<h1>Polymarket Trading Agent</h1>
<p>Dashboard build not available. API is running.</p>
<p><a href="/docs">API Documentation</a> | <a href="/health">Health Check</a></p>
</body></html>
FALLBACK
    chown "$APP_USER:$APP_USER" "${APP_DIR}/dashboard/dist/index.html"
fi

# ─── 7. Nginx Configuration ─────────────────────────────────
log "Step 7/13: Configuring nginx..."

# Stop Caddy if it's running (conflicts with nginx on port 80)
if systemctl is-active --quiet caddy 2>/dev/null; then
    warn "Caddy is running on port 80 — stopping and disabling it..."
    systemctl stop caddy
    systemctl disable caddy
    log "Caddy stopped."
fi

cp "${APP_DIR}/scripts/nginx-polymarket.conf" /etc/nginx/sites-available/polymarket
ln -sf /etc/nginx/sites-available/polymarket /etc/nginx/sites-enabled/polymarket
rm -f /etc/nginx/sites-enabled/default

# Replace placeholder with actual dashboard build path
sed -i "s|__APP_DIR__|${APP_DIR}|g" /etc/nginx/sites-available/polymarket

if nginx -t; then
    systemctl enable nginx
    systemctl restart nginx
    log "Nginx configured and running."
else
    warn "Nginx config test failed — check /etc/nginx/sites-available/polymarket"
fi

# ─── 8. Redis ───────────────────────────────────────────────
log "Step 8/13: Configuring Redis..."
systemctl enable redis-server
systemctl start redis-server
redis-cli ping > /dev/null 2>&1 && log "Redis is running." || warn "Redis may not be running."

# ─── 9. Systemd Services ────────────────────────────────────
log "Step 9/13: Setting up systemd services..."

# API service
cat > /etc/systemd/system/polymarket-agent.service << 'UNIT'
[Unit]
Description=Polymarket Trading Agent API
After=network.target redis-server.service
Wants=redis-server.service

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/polymarket-agent
EnvironmentFile=/home/ubuntu/polymarket-agent/.env
ExecStart=/home/ubuntu/polymarket-agent/venv/bin/python run.py
Restart=on-failure
RestartSec=5
StartLimitBurst=3
StartLimitIntervalSec=60

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/home/ubuntu/polymarket-agent/logs /home/ubuntu/polymarket-agent/trading.db /home/ubuntu/polymarket-agent/backups
PrivateTmp=true

# Logging
StandardOutput=append:/home/ubuntu/polymarket-agent/logs/agent.log
StandardError=append:/home/ubuntu/polymarket-agent/logs/agent-error.log

[Install]
WantedBy=multi-user.target
UNIT

# Dashboard dev server (optional, disabled by default)
cat > /etc/systemd/system/polymarket-dashboard.service << 'UNIT'
[Unit]
Description=Polymarket Dashboard Dev Server (Vite)
After=network.target polymarket-agent.service

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/polymarket-agent/dashboard
ExecStart=/usr/bin/npx vite --host 0.0.0.0
Restart=on-failure
RestartSec=5
StandardOutput=append:/home/ubuntu/polymarket-agent/logs/dashboard.log
StandardError=append:/home/ubuntu/polymarket-agent/logs/dashboard-error.log

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable polymarket-agent
log "Systemd services configured."

# ─── 10. Database Migrations ────────────────────────────────
log "Step 10/13: Running database migrations..."
cd "$APP_DIR"
mkdir -p logs backups

# Create tables directly (Alembic for future schema changes)
if sudo -u "$APP_USER" "${APP_DIR}/venv/bin/python" -c "
import asyncio
from src.data.database import create_engine, create_tables
from src.config import StaticConfig
async def init():
    config = StaticConfig()
    engine = await create_engine(config.database_url)
    await create_tables(engine)
    await engine.dispose()
    print('  Database tables created.')
asyncio.run(init())
"; then
    log "Database tables created."
else
    warn "Database migration failed — tables may already exist or module import error."
fi

# ─── 11. Seed Data ──────────────────────────────────────────
log "Step 11/13: Seeding test market data..."
cd "$APP_DIR"
if sudo -u "$APP_USER" "${APP_DIR}/venv/bin/python" -m scripts.seed_markets; then
    log "Seed data loaded."
else
    warn "Seed script failed — non-critical, continuing."
fi

# ─── 12. Prometheus + Grafana ────────────────────────────────
log "Step 12/13: Setting up monitoring..."

# Prometheus config for scraping local metrics
cat > /etc/prometheus/polymarket.yml << 'PROM'
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'polymarket-agent'
    metrics_path: '/internal/metrics'
    static_configs:
      - targets: ['localhost:8000']
        labels:
          instance: 'trading-agent'

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['localhost:9100']
PROM

# Update prometheus to use our config
if [[ -f /etc/default/prometheus ]]; then
    sed -i 's|ARGS=.*|ARGS="--config.file=/etc/prometheus/polymarket.yml --storage.tsdb.retention.time=30d"|' /etc/default/prometheus
fi

systemctl enable prometheus
systemctl restart prometheus || warn "Prometheus restart failed — check config."

# Grafana (optional — install if not present)
if ! command -v grafana-server &>/dev/null; then
    log "Installing Grafana..."
    apt-get install -y -qq adduser libfontconfig1 musl
    wget -q "https://dl.grafana.com/oss/release/grafana_11.4.0_amd64.deb" -O /tmp/grafana.deb 2>/dev/null && \
        dpkg -i /tmp/grafana.deb && \
        systemctl enable grafana-server && \
        systemctl start grafana-server && \
        log "Grafana installed on port 3001." || \
        warn "Grafana install failed — skip for now, install manually later."
    rm -f /tmp/grafana.deb
fi

# ─── 13. Start Services & Verify ────────────────────────────
log "Step 13/13: Starting services..."
systemctl start polymarket-agent
sleep 3

# Health check
HEALTH=$(curl -s -m 5 http://localhost:8000/health 2>/dev/null || echo "")
if echo "$HEALTH" | grep -q '"status":"ok"'; then
    log "API is healthy!"
else
    warn "API health check failed. Check logs: journalctl -u polymarket-agent -f"
fi

# ─── Setup backup cron ──────────────────────────────────────
if [[ -f "${APP_DIR}/scripts/backup.sh" ]]; then
    chmod +x "${APP_DIR}/scripts/backup.sh"
    # Daily backup at 2 AM
    (crontab -u "$APP_USER" -l 2>/dev/null; echo "0 2 * * * ${APP_DIR}/scripts/backup.sh") | sort -u | crontab -u "$APP_USER" -
    log "Daily backup cron job installed."
fi

# Health check cron
if [[ -f "${APP_DIR}/scripts/health_check.sh" ]]; then
    chmod +x "${APP_DIR}/scripts/health_check.sh"
    # Every 5 minutes
    (crontab -u "$APP_USER" -l 2>/dev/null; echo "*/5 * * * * ${APP_DIR}/scripts/health_check.sh") | sort -u | crontab -u "$APP_USER" -
    log "Health check cron job installed."
fi

# ─── Summary ─────────────────────────────────────────────────
PUBLIC_IP=$(curl -s -m 5 http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo "YOUR_IP")
echo ""
echo "=========================================="
echo -e "${GREEN}  Polymarket Agent Deployed!${NC}"
echo "=========================================="
echo ""
echo "  Dashboard:    http://${PUBLIC_IP}"
echo "  API Health:   http://${PUBLIC_IP}/health"
echo "  API Docs:     http://${PUBLIC_IP}/docs"
echo "  Prometheus:   http://${PUBLIC_IP}:9090"
echo "  Grafana:      http://${PUBLIC_IP}:3001 (admin/admin)"
echo ""
echo "  Manage services:"
echo "    sudo systemctl status polymarket-agent"
echo "    sudo systemctl restart polymarket-agent"
echo "    sudo journalctl -u polymarket-agent -f"
echo ""
echo "  For Vite dev server (hot reload):"
echo "    sudo systemctl start polymarket-dashboard"
echo "    Access: http://${PUBLIC_IP}:3000"
echo ""
echo "  IMPORTANT: Edit ${APP_DIR}/.env to add your API keys!"
echo "=========================================="
