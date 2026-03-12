#!/bin/bash
########################################################################
# Polymarket Agent + Agent Zero — Full Server Setup
# Run on a fresh Ubuntu 22.04+ server (EC2, VPS, etc.)
#
# Usage:  bash full-setup.sh
#
# What this does:
#   1. Ensures swap & system deps
#   2. Clones & installs Polymarket Agent + Agent Zero
#   3. Installs Playwright, Claude Code CLI
#   4. Starts Redis
#   5. Creates launcher scripts
#   6. Asks for API keys LAST (after everything is installed)
#   7. Writes .env files and prints summary
########################################################################

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════╗"
echo "║   Polymarket Agent + Agent Zero — Full Setup        ║"
echo "╚══════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Detect server IP early (no user input needed)
SERVER_IP=$(curl -s http://checkip.amazonaws.com 2>/dev/null || curl -s ifconfig.me 2>/dev/null || echo "localhost")
echo -e "  Server IP: ${CYAN}${SERVER_IP}${NC}"
echo ""

# Generate secrets (no user input needed)
REDIS_PASS=$(openssl rand -hex 16)
JWT_SECRET=$(openssl rand -hex 32)

########################################################################
# STEP 1: Ensure swap exists (prevents "No space left" during builds)
########################################################################
if ! swapon --show | grep -q '/swapfile'; then
    echo -e "${CYAN}[1/8] Creating swap space...${NC}"
    sudo fallocate -l 4G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
    echo -e "${GREEN}[OK] 4GB swap enabled${NC}"
else
    echo -e "${GREEN}[1/8] Swap already exists — OK${NC}"
fi

########################################################################
# STEP 2: Install system dependencies
########################################################################
echo -e "${CYAN}[2/8] Installing system dependencies...${NC}"

sudo apt update -qq

# Remove conflicting npm package if present (NodeSource nodejs bundles npm)
sudo apt remove -y npm 2>/dev/null || true

sudo apt install -y -qq \
    git python3.11 python3.11-venv python3.11-dev python3-pip \
    nodejs \
    redis-server \
    curl wget unzip \
    build-essential libffi-dev libssl-dev \
    \
    ufw || true

# Install chromium (try apt then snap)
sudo apt install -y -qq chromium-browser 2>/dev/null || sudo snap install chromium 2>/dev/null || true

# Redis — configure password and start
sudo sed -i "s/^# requirepass .*/requirepass ${REDIS_PASS}/" /etc/redis/redis.conf
sudo sed -i "s/^requirepass .*/requirepass ${REDIS_PASS}/" /etc/redis/redis.conf
sudo systemctl enable redis-server
sudo systemctl restart redis-server

echo -e "${GREEN}[OK] System deps installed${NC}"

########################################################################
# STEP 3: Clone & install Polymarket Agent
########################################################################
echo -e "${CYAN}[3/8] Installing Polymarket Agent...${NC}"

cd ~
if [[ -d polymarket-agent ]]; then
    cd polymarket-agent && git pull origin main 2>/dev/null || true
else
    git clone https://github.com/elkanaevdaniel-ui/polymarket-agent.git
    cd polymarket-agent
fi

python3.11 -m venv venv
source venv/bin/activate
echo -e "  Installing Python packages (this may take 5-10 minutes)..."
pip install --no-cache-dir -r requirements.txt 2>&1 | while read -r line; do
    if [[ "$line" == *"Successfully installed"* ]] || [[ "$line" == *"Collecting"* ]]; then
        echo -e "  ${line}"
    fi
done
deactivate

echo -e "${GREEN}[OK] Polymarket Agent installed${NC}"

########################################################################
# STEP 4: Clone & install Agent Zero
########################################################################
echo -e "${CYAN}[4/8] Installing Agent Zero...${NC}"

cd ~
if [[ -d agent-zero ]]; then
    cd agent-zero && git pull origin main 2>/dev/null || true
else
    git clone https://github.com/frdel/agent-zero.git
    cd agent-zero
fi

python3.11 -m venv venv
source venv/bin/activate
echo -e "  Upgrading pip..."
pip install --no-cache-dir --upgrade pip setuptools wheel 2>&1 | tail -1
echo -e "  Installing scipy & numpy (may take a few minutes)..."
pip install --no-cache-dir "scipy>=1.11,<2" "numpy>=1.24,<2" 2>&1 | tail -1
echo -e "  Installing Agent Zero packages (this may take 10-15 minutes)..."
pip install --no-cache-dir -r requirements.txt 2>&1 | while read -r line; do
    if [[ "$line" == *"Successfully installed"* ]] || [[ "$line" == *"Collecting"* ]]; then
        echo -e "  ${line}"
    fi
done
deactivate

echo -e "${GREEN}[OK] Agent Zero installed${NC}"

########################################################################
# STEP 5: Install Playwright browsers
########################################################################
echo -e "${CYAN}[5/8] Installing Playwright browsers...${NC}"

# For Agent Zero
source ~/agent-zero/venv/bin/activate
pip install -q --no-cache-dir playwright
playwright install chromium
playwright install-deps 2>/dev/null || sudo playwright install-deps
deactivate

# For Polymarket Agent
source ~/polymarket-agent/venv/bin/activate
pip install -q --no-cache-dir playwright
playwright install chromium
deactivate

echo -e "${GREEN}[OK] Playwright browsers installed${NC}"

########################################################################
# STEP 6: Install Claude Code CLI
########################################################################
echo -e "${CYAN}[6/8] Installing Claude Code CLI...${NC}"

sudo npm install -g @anthropic-ai/claude-code 2>/dev/null || npm install -g @anthropic-ai/claude-code

echo -e "${GREEN}[OK] Claude Code installed${NC}"

########################################################################
# STEP 7: Verify Redis, create launchers, firewall
########################################################################
echo -e "${CYAN}[7/8] Setting up services & launchers...${NC}"

# Redis — already started in step 2, verify it's running
if redis-cli -a "${REDIS_PASS}" ping 2>/dev/null | grep -q PONG; then
    echo -e "  ${GREEN}Redis is running${NC}"
else
    echo -e "  ${RED}Redis failed to start — check: sudo systemctl status redis-server${NC}"
fi

# Bridge instructions for Agent Zero
mkdir -p ~/agent-zero/work_dir
cat > ~/agent-zero/work_dir/INSTRUCTIONS.md << MDEOF
# Polymarket Trading Agent — Instructions for Agent Zero

## Project location
~/polymarket-agent

## How to run the trading bot
\`\`\`bash
source ~/polymarket-agent/venv/bin/activate
cd ~/polymarket-agent
python run.py
\`\`\`

## How to run tests
\`\`\`bash
source ~/polymarket-agent/venv/bin/activate
cd ~/polymarket-agent
pytest
\`\`\`

## How to check the dashboard
Open http://${SERVER_IP}:8000 in the browser

## How to browse Polymarket
Open https://polymarket.com in the browser — full access, no restrictions

## Environment
All API keys are configured in ~/polymarket-agent/.env
All keys are also in ~/agent-zero/.env
Never ask the user for API keys — they are already set.

## Available tools
- Browse any website (Playwright)
- Run Python code
- Execute shell commands
- Read/write files
- Call Polymarket API, Anthropic API, etc.
MDEOF

# Launcher scripts
cat > ~/start-agent-zero.sh << 'SCRIPT'
#!/bin/bash
cd ~/agent-zero
source venv/bin/activate
python run_ui.py
SCRIPT
chmod +x ~/start-agent-zero.sh

cat > ~/start-polymarket.sh << 'SCRIPT'
#!/bin/bash
cd ~/polymarket-agent
source venv/bin/activate
python run.py
SCRIPT
chmod +x ~/start-polymarket.sh

cat > ~/start-claude.sh << 'SCRIPT'
#!/bin/bash
export ANTHROPIC_API_KEY=$(grep ANTHROPIC_API_KEY ~/polymarket-agent/.env | cut -d= -f2)
cd ~/polymarket-agent
claude
SCRIPT
chmod +x ~/start-claude.sh

cat > ~/start-all.sh << 'SCRIPT'
#!/bin/bash
echo "Ensuring Redis is running..."
sudo systemctl start redis-server

echo "Starting Agent Zero (background)..."
cd ~/agent-zero && source venv/bin/activate && python run_ui.py &
AZ_PID=$!

echo "Starting Polymarket Dashboard (background)..."
cd ~/polymarket-agent && source venv/bin/activate && python run.py &
PM_PID=$!

SERVER_IP=$(curl -s http://checkip.amazonaws.com)
echo ""
echo "═══════════════════════════════════════════════════"
echo "  All services running!"
echo "  Agent Zero UI:       http://${SERVER_IP}:50001"
echo "  Polymarket Dashboard: http://${SERVER_IP}:8000"
echo "  Claude Code:          run ~/start-claude.sh"
echo "═══════════════════════════════════════════════════"
echo ""
echo "Press Ctrl+C to stop all"
wait $AZ_PID $PM_PID
SCRIPT
chmod +x ~/start-all.sh

# Git config for auto-push (Agent Zero delegates coding to Claude Code which commits)
cd ~/polymarket-agent
git config pull.rebase true
git config push.default current
# If git user not set, set a default
git config user.name 2>/dev/null || git config user.name "Polymarket Agent"
git config user.email 2>/dev/null || git config user.email "agent@polymarket-bot.local"

# Firewall
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 8000/tcp  # Polymarket dashboard
sudo ufw allow 50001/tcp # Agent Zero UI
sudo ufw --force enable

echo -e "${GREEN}[OK] Services, launchers & firewall ready${NC}"

########################################################################
# STEP 8: Collect API keys and write .env files
########################################################################
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Installation complete! Now let's configure keys.  ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}[KEYS] Enter your API keys. You'll only do this ONCE.${NC}"
echo -e "${YELLOW}       Press Enter to skip any optional key.${NC}"
echo ""

# Anthropic (required)
read -p "Anthropic API key (sk-ant-...): " ANTHROPIC_KEY
while [[ -z "$ANTHROPIC_KEY" ]]; do
    echo -e "${RED}Required! Get one at https://console.anthropic.com/settings/keys${NC}"
    read -p "Anthropic API key: " ANTHROPIC_KEY
done

# OpenAI (optional — needed for embeddings)
read -p "OpenAI API key (sk-... or Enter to skip): " OPENAI_KEY

# OpenRouter (optional — enables free models for utility tasks)
read -p "OpenRouter API key (sk-or-... or Enter to skip): " OPENROUTER_KEY

# Polymarket wallet (optional)
read -p "Polymarket wallet private key (0x... or Enter for paper trading): " PM_KEY

# News API (optional)
read -p "News API key (Enter to skip): " NEWS_KEY

# SERP API (optional)
read -p "SERP API key (Enter to skip): " SERP_KEY

# Google API (optional)
read -p "Google API key (Enter to skip): " GOOGLE_KEY

# Telegram (optional)
read -p "Telegram bot token (Enter to skip): " TG_TOKEN
TG_CHAT=""
if [[ -n "$TG_TOKEN" ]]; then
    read -p "Telegram chat ID: " TG_CHAT
fi

echo ""
echo -e "${CYAN}Writing .env files...${NC}"

# Write Polymarket Agent .env
cat > ~/polymarket-agent/.env << ENVEOF
# ═══════════════════════════════════════════════════════════
# Polymarket Agent — Auto-generated by full-setup.sh
# Generated: $(date -u +"%Y-%m-%d %H:%M:%S UTC")
# Server: ${SERVER_IP}
# ═══════════════════════════════════════════════════════════

# Trading Mode
TRADING_MODE=${PM_KEY:+live}${PM_KEY:-paper}
INITIAL_BANKROLL=1000.0

# Polymarket API
POLYMARKET_PRIVATE_KEY=${PM_KEY}
POLYMARKET_PROXY_ADDRESS=
POLYMARKET_HOST=https://clob.polymarket.com
POLYMARKET_CHAIN_ID=137
GAMMA_API_URL=https://gamma-api.polymarket.com

# LLM Providers
ANTHROPIC_API_KEY=${ANTHROPIC_KEY}
OPENAI_API_KEY=${OPENAI_KEY}
GOOGLE_API_KEY=${GOOGLE_KEY}
OPENROUTER_API_KEY=${OPENROUTER_KEY}

# Database
DATABASE_URL=sqlite+aiosqlite:///./trading.db

# Redis
REDIS_URL=redis://localhost:6379
REDIS_PASSWORD=${REDIS_PASS}

# Security
DASHBOARD_JWT_SECRET=${JWT_SECRET}
DASHBOARD_JWT_EXPIRE_MINUTES=60

# Telegram
TELEGRAM_BOT_TOKEN=${TG_TOKEN}
TELEGRAM_CHAT_ID=${TG_CHAT}

# Signal Sources
NEWS_API_KEY=${NEWS_KEY}
SERP_API_KEY=${SERP_KEY}
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
TWITTER_BEARER_TOKEN=

# CORS
CORS_ORIGINS=http://localhost:3000,http://localhost:8082,http://${SERVER_IP},http://${SERVER_IP}:3000,http://${SERVER_IP}:8000

# Deployment
BEHIND_PROXY=false
HOST=0.0.0.0
PORT=8000
ENVEOF

# Write Agent Zero .env
cat > ~/agent-zero/.env << ENVEOF
# ═══════════════════════════════════════════════════════════
# Agent Zero — Auto-generated by full-setup.sh
# Generated: $(date -u +"%Y-%m-%d %H:%M:%S UTC")
# ═══════════════════════════════════════════════════════════

# ─── Chat Model: Claude Opus 4.6 (most capable, for complex reasoning) ───
CHAT_MODEL_PROVIDER=anthropic
CHAT_MODEL_NAME=claude-opus-4-6

# ─── Utility Model: OpenRouter FREE tier (cost saving for simple tasks) ───
UTILITY_MODEL_PROVIDER=openrouter
UTILITY_MODEL_NAME=google/gemini-2.0-flash-exp:free

# ─── Embedding Model: OpenAI (cheapest, best quality) ───
EMBEDDING_MODEL_PROVIDER=openai
EMBEDDING_MODEL_NAME=text-embedding-3-small

# API Keys
API_KEY_ANTHROPIC=${ANTHROPIC_KEY}
API_KEY_OPENAI=${OPENAI_KEY}
API_KEY_GOOGLE=${GOOGLE_KEY}
API_KEY_OPENROUTER=${OPENROUTER_KEY}

# Browser
BROWSER_ENABLED=true

# Agent Zero Web UI
WEB_UI_PORT=50001
ENVEOF

# Set Anthropic key for Claude Code
mkdir -p ~/.config
grep -q "ANTHROPIC_API_KEY" ~/.bashrc 2>/dev/null && \
    sed -i "s|export ANTHROPIC_API_KEY=.*|export ANTHROPIC_API_KEY=${ANTHROPIC_KEY}|" ~/.bashrc || \
    echo "export ANTHROPIC_API_KEY=${ANTHROPIC_KEY}" >> ~/.bashrc

echo -e "${GREEN}[OK] All .env files written${NC}"

########################################################################
# DONE
########################################################################
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║            SETUP COMPLETE!                          ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  Server IP:              ${CYAN}${SERVER_IP}${NC}"
echo ""
echo -e "  ${YELLOW}Quick Start Commands:${NC}"
echo -e "    ~/start-all.sh         — Start everything"
echo -e "    ~/start-agent-zero.sh  — Agent Zero only"
echo -e "    ~/start-polymarket.sh  — Trading bot only"
echo -e "    ~/start-claude.sh      — Claude Code CLI"
echo ""
echo -e "  ${YELLOW}URLs (after starting):${NC}"
echo -e "    Agent Zero UI:          http://${SERVER_IP}:50001"
echo -e "    Polymarket Dashboard:   http://${SERVER_IP}:8000"
echo ""
echo -e "  ${YELLOW}Key Files:${NC}"
echo -e "    Polymarket config:      ~/polymarket-agent/.env"
echo -e "    Agent Zero config:      ~/agent-zero/.env"
echo ""
echo -e "  ${RED}Security Reminders:${NC}"
echo -e "    - TRADING_MODE is set to: ${PM_KEY:+live}${PM_KEY:-paper}"
echo -e "    - Use SSH tunnel for Agent Zero: ssh -L 50001:localhost:50001 ubuntu@${SERVER_IP}"
echo -e "    - Never share your .env files"
echo ""
echo -e "${GREEN}Run ~/start-all.sh to launch everything!${NC}"
