#!/bin/bash
########################################################################
# System Info — Show everything installed on this server
# Usage:  bash scripts/system-info.sh
########################################################################

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════╗"
echo "║          System Info — Full Inventory                ║"
echo "╚══════════════════════════════════════════════════════╝"
echo -e "${NC}"

########################################################################
echo -e "${YELLOW}═══ OS & Hardware ═══${NC}"
echo -e "  OS:        $(lsb_release -ds 2>/dev/null || cat /etc/os-release | grep PRETTY_NAME | cut -d= -f2 | tr -d '"')"
echo -e "  Kernel:    $(uname -r)"
echo -e "  Arch:      $(uname -m)"
echo -e "  CPU:       $(nproc) cores"
echo -e "  RAM:       $(free -h | awk '/Mem:/ {printf "%s total, %s free", $2, $4}')"
echo -e "  Swap:      $(free -h | awk '/Swap:/ {printf "%s total, %s free", $2, $4}')"
echo -e "  Disk:      $(df -h / | awk 'NR==2 {printf "%s total, %s free (%s used)", $2, $4, $5}')"
echo -e "  Server IP: $(curl -s http://checkip.amazonaws.com 2>/dev/null || echo 'unknown')"
echo ""

########################################################################
echo -e "${YELLOW}═══ Python ═══${NC}"
for py in python3 python3.11 python3.12; do
    if command -v $py &>/dev/null; then
        echo -e "  $py:  $($py --version 2>&1)"
    fi
done
echo -e "  pip:       $(pip --version 2>/dev/null | head -1 || echo 'not installed')"
echo ""

########################################################################
echo -e "${YELLOW}═══ Node.js & npm ═══${NC}"
echo -e "  node:      $(node --version 2>/dev/null || echo 'not installed')"
echo -e "  npm:       $(npm --version 2>/dev/null || echo 'not installed')"
echo ""

########################################################################
echo -e "${YELLOW}═══ Key Services ═══${NC}"

# Redis
if command -v redis-server &>/dev/null; then
    REDIS_VER=$(redis-server --version 2>/dev/null | awk '{print $3}' | cut -d= -f2)
    REDIS_STATUS=$(systemctl is-active redis-server 2>/dev/null || echo "unknown")
    echo -e "  Redis:     v${REDIS_VER} (${REDIS_STATUS})"
    if [[ "$REDIS_STATUS" == "active" ]]; then
        echo -e "             $(redis-cli INFO server 2>/dev/null | grep tcp_port | tr -d '\r' || echo 'port unknown')"
    fi
else
    echo -e "  Redis:     ${RED}not installed${NC}"
fi

# Docker (should NOT be here)
if command -v docker &>/dev/null; then
    echo -e "  Docker:    ${RED}$(docker --version 2>/dev/null)${NC} ← REMOVE THIS"
else
    echo -e "  Docker:    ${GREEN}not installed (good)${NC}"
fi
if command -v docker-compose &>/dev/null; then
    echo -e "  docker-compose: ${RED}$(docker-compose --version 2>/dev/null)${NC} ← REMOVE THIS"
else
    echo -e "  docker-compose: ${GREEN}not installed (good)${NC}"
fi

# UFW firewall
if command -v ufw &>/dev/null; then
    UFW_STATUS=$(sudo ufw status 2>/dev/null | head -1)
    echo -e "  Firewall:  ${UFW_STATUS}"
    sudo ufw status numbered 2>/dev/null | grep -E "^\[" | while read -r line; do
        echo -e "             ${line}"
    done
fi
echo ""

########################################################################
echo -e "${YELLOW}═══ Project Directories ═══${NC}"
for dir in ~/polymarket-agent ~/agent-zero; do
    if [[ -d "$dir" ]]; then
        BRANCH=$(cd "$dir" && git branch --show-current 2>/dev/null || echo "?")
        COMMIT=$(cd "$dir" && git log -1 --format="%h %s" 2>/dev/null || echo "?")
        echo -e "  ${GREEN}$dir${NC}"
        echo -e "    branch: ${BRANCH}"
        echo -e "    latest: ${COMMIT}"
    else
        echo -e "  ${RED}$dir — not found${NC}"
    fi
done
echo ""

########################################################################
echo -e "${YELLOW}═══ Python Virtual Environments ═══${NC}"
for dir in ~/polymarket-agent ~/agent-zero; do
    VENV="$dir/venv"
    if [[ -d "$VENV" ]]; then
        PY_VER=$("$VENV/bin/python" --version 2>/dev/null || echo "?")
        PKG_COUNT=$("$VENV/bin/pip" list --format=columns 2>/dev/null | tail -n +3 | wc -l)
        echo -e "  ${GREEN}$VENV${NC} — ${PY_VER}, ${PKG_COUNT} packages"
    else
        echo -e "  ${RED}$VENV — not found${NC}"
    fi
done
echo ""

########################################################################
echo -e "${YELLOW}═══ Polymarket Agent — Key Python Packages ═══${NC}"
VENV=~/polymarket-agent/venv
if [[ -d "$VENV" ]]; then
    for pkg in httpx pydantic anthropic py-clob-client fastapi uvicorn loguru aiohttp websockets sqlalchemy alembic; do
        VER=$("$VENV/bin/pip" show "$pkg" 2>/dev/null | grep "^Version:" | awk '{print $2}')
        if [[ -n "$VER" ]]; then
            echo -e "  ${GREEN}${pkg}${NC}: ${VER}"
        else
            echo -e "  ${RED}${pkg}: not installed${NC}"
        fi
    done
else
    echo -e "  ${RED}venv not found${NC}"
fi
echo ""

########################################################################
echo -e "${YELLOW}═══ Agent Zero — Key Python Packages ═══${NC}"
VENV=~/agent-zero/venv
if [[ -d "$VENV" ]]; then
    for pkg in langchain openai anthropic playwright chromadb flask; do
        VER=$("$VENV/bin/pip" show "$pkg" 2>/dev/null | grep "^Version:" | awk '{print $2}')
        if [[ -n "$VER" ]]; then
            echo -e "  ${GREEN}${pkg}${NC}: ${VER}"
        else
            echo -e "  ${RED}${pkg}: not installed${NC}"
        fi
    done
else
    echo -e "  ${RED}venv not found${NC}"
fi
echo ""

########################################################################
echo -e "${YELLOW}═══ Playwright Browsers ═══${NC}"
for VENV in ~/polymarket-agent/venv ~/agent-zero/venv; do
    if [[ -f "$VENV/bin/playwright" ]]; then
        echo -e "  ${CYAN}$(dirname $(dirname $VENV))/$(basename $(dirname $VENV)):${NC}"
        "$VENV/bin/python" -m playwright install --dry-run 2>/dev/null | head -5 || \
            ls ~/.cache/ms-playwright/ 2>/dev/null | while read -r b; do echo "    $b"; done
    fi
done
if [[ -d ~/.cache/ms-playwright ]]; then
    echo -e "  Cache: $(du -sh ~/.cache/ms-playwright 2>/dev/null | awk '{print $1}')"
else
    echo -e "  ${RED}No browser cache found${NC}"
fi
echo ""

########################################################################
echo -e "${YELLOW}═══ Claude Code CLI ═══${NC}"
if command -v claude &>/dev/null; then
    echo -e "  ${GREEN}$(claude --version 2>/dev/null || echo 'installed')${NC}"
else
    echo -e "  ${RED}not installed${NC}"
fi
echo ""

########################################################################
echo -e "${YELLOW}═══ .env Files ═══${NC}"
for envfile in ~/polymarket-agent/.env ~/agent-zero/.env; do
    if [[ -f "$envfile" ]]; then
        KEYS_SET=$(grep -v '^#' "$envfile" | grep -v '^$' | grep -v '=$' | wc -l)
        KEYS_EMPTY=$(grep -v '^#' "$envfile" | grep '=$' | wc -l)
        echo -e "  ${GREEN}${envfile}${NC}: ${KEYS_SET} keys set, ${KEYS_EMPTY} empty"
    else
        echo -e "  ${RED}${envfile} — not found${NC}"
    fi
done
echo ""

########################################################################
echo -e "${YELLOW}═══ Launcher Scripts ═══${NC}"
for script in ~/start-all.sh ~/start-agent-zero.sh ~/start-polymarket.sh ~/start-claude.sh; do
    if [[ -f "$script" ]]; then
        echo -e "  ${GREEN}$(basename $script)${NC} — exists"
    else
        echo -e "  ${RED}$(basename $script) — missing${NC}"
    fi
done
echo ""

########################################################################
echo -e "${YELLOW}═══ Listening Ports ═══${NC}"
ss -tlnp 2>/dev/null | grep LISTEN | awk '{print "  " $4 " — " $6}' | sed 's/users://' | head -15
echo ""

########################################################################
echo -e "${YELLOW}═══ Running Docker Containers (should be empty) ═══${NC}"
if command -v docker &>/dev/null; then
    CONTAINERS=$(sudo docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}" 2>/dev/null)
    if [[ -n "$CONTAINERS" ]]; then
        echo -e "  ${RED}${CONTAINERS}${NC}"
        echo -e "  ${YELLOW}Run: sudo docker stop \$(sudo docker ps -q) to stop them${NC}"
    else
        echo -e "  ${GREEN}No containers running${NC}"
    fi
else
    echo -e "  ${GREEN}Docker not installed — nothing to check${NC}"
fi
echo ""

########################################################################
echo -e "${YELLOW}═══ Disk Usage Breakdown ═══${NC}"
echo -e "  $(du -sh ~/polymarket-agent 2>/dev/null | awk '{print "polymarket-agent: " $1}')"
echo -e "  $(du -sh ~/agent-zero 2>/dev/null | awk '{print "agent-zero:       " $1}')"
echo -e "  $(du -sh ~/.cache/ms-playwright 2>/dev/null | awk '{print "playwright cache: " $1}')"
echo -e "  $(du -sh /var/lib/docker 2>/dev/null | awk '{print "docker data:      " $1}' || echo 'docker data:      0')"
echo ""

echo -e "${GREEN}═══ Done ═══${NC}"
