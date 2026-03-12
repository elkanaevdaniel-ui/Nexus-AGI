#!/usr/bin/env bash
# ==============================================================================
# install-claude-code-tool.sh
# Installs the Enhanced Claude Code CLI tool + memory system into Agent Zero
# ==============================================================================
# Run this ON THE EC2 INSTANCE where Agent Zero lives:
#   bash ~/polymarket-agent/scripts/install-claude-code-tool.sh
# ==============================================================================

set -uo pipefail

AGENT_ZERO_DIR="${AGENT_ZERO_DIR:-/home/ubuntu/agent-zero}"
POLYMARKET_DIR="${POLYMARKET_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
PROFILE_DIR="$POLYMARKET_DIR/agent-zero-profile"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=========================================="
echo "Installing Enhanced A0-Claude Pipeline v2"
echo "=========================================="
echo ""

# ---------- Pre-checks ----------
ERRORS=0

if [ ! -d "$AGENT_ZERO_DIR" ]; then
    echo -e "${RED}ERROR${NC}: Agent Zero not found at $AGENT_ZERO_DIR"
    echo "Set AGENT_ZERO_DIR env var if it's in a different location."
    exit 1
fi
echo -e "${GREEN}✓${NC} Agent Zero found at $AGENT_ZERO_DIR"

if command -v claude &>/dev/null; then
    CLAUDE_VERSION=$(claude --version 2>&1 | head -1 || echo "unknown")
    echo -e "${GREEN}✓${NC} Claude Code CLI installed: $CLAUDE_VERSION"
else
    echo -e "${RED}✗${NC} Claude Code CLI NOT installed"
    echo "  Install: npm install -g @anthropic-ai/claude-code"
    ERRORS=$((ERRORS + 1))
fi

if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
    echo -e "${GREEN}✓${NC} ANTHROPIC_API_KEY is set (${ANTHROPIC_API_KEY:0:10}...)"
else
    echo -e "${YELLOW}⚠${NC} ANTHROPIC_API_KEY not set in current shell"
    echo "  Make sure it's in Agent Zero's .env or environment"
fi

for f in "$PROFILE_DIR/claude_code_cli.py" "$PROFILE_DIR/agent.system.tool.claude_code.md"; do
    if [ ! -f "$f" ]; then
        echo -e "${RED}✗${NC} Source file missing: $f"
        ERRORS=$((ERRORS + 1))
    fi
done

if [ $ERRORS -gt 0 ]; then
    echo ""
    echo -e "${RED}Cannot install — fix the errors above first.${NC}"
    exit 1
fi

echo ""

# ---------- 1. Install tool file ----------
echo "--- Step 1: Installing enhanced Claude Code CLI tool ---"
cp "$PROFILE_DIR/claude_code_cli.py" "$AGENT_ZERO_DIR/python/tools/claude_code_cli.py"
echo -e "${GREEN}✓${NC} Copied claude_code_cli.py → $AGENT_ZERO_DIR/python/tools/"

# ---------- 2. Install tool prompt ----------
echo "--- Step 2: Installing tool prompt ---"
cp "$PROFILE_DIR/agent.system.tool.claude_code.md" "$AGENT_ZERO_DIR/prompts/agent.system.tool.claude_code.md"
echo -e "${GREEN}✓${NC} Copied agent.system.tool.claude_code.md → $AGENT_ZERO_DIR/prompts/"

# ---------- 3. Install behaviour + role + environment profiles ----------
echo "--- Step 3: Installing Agent Zero profiles ---"
for profile in agent.system.main.behaviour.md agent.system.main.role.md agent.system.main.environment.md; do
    if [ -f "$PROFILE_DIR/$profile" ]; then
        cp "$PROFILE_DIR/$profile" "$AGENT_ZERO_DIR/prompts/$profile"
        echo -e "${GREEN}✓${NC} Copied $profile → $AGENT_ZERO_DIR/prompts/"
    fi
done

# ---------- 4. Set up memory system ----------
echo "--- Step 4: Setting up memory system (SQLite + Redis) ---"
bash "$POLYMARKET_DIR/scripts/setup_a0_memory.sh"

# ---------- 5. Switch to local embeddings (free) ----------
echo "--- Step 5: Configuring local embeddings ---"

# 5a. Install sentence-transformers in Agent Zero's venv (required for local embeddings)
A0_VENV="$AGENT_ZERO_DIR/venv"
if [ -d "$A0_VENV" ]; then
    echo "  Installing sentence-transformers in Agent Zero venv..."
    "$A0_VENV/bin/pip" install -q sentence-transformers 2>/dev/null
    if "$A0_VENV/bin/python" -c "import sentence_transformers" 2>/dev/null; then
        echo -e "${GREEN}✓${NC} sentence-transformers installed in Agent Zero venv"
    else
        echo -e "${YELLOW}⚠${NC} sentence-transformers install may have failed — check manually"
    fi
else
    echo -e "${YELLOW}⚠${NC} Agent Zero venv not found at $A0_VENV — install sentence-transformers manually"
fi

# 5b. Set embedding config in Agent Zero .env
A0_ENV="$AGENT_ZERO_DIR/usr/.env"
if [ -f "$A0_ENV" ]; then
    # Provider must be "huggingface" for litellm to route to local sentence-transformers
    if grep -q "A0_SET_embed_model_provider" "$A0_ENV"; then
        sed -i 's/A0_SET_embed_model_provider=.*/A0_SET_embed_model_provider=huggingface/' "$A0_ENV"
    else
        echo "A0_SET_embed_model_provider=huggingface" >> "$A0_ENV"
    fi
    # Model name: litellm expects "huggingface/model-name" format for HF embeddings
    if grep -q "A0_SET_embed_model_name" "$A0_ENV"; then
        sed -i 's|A0_SET_embed_model_name=.*|A0_SET_embed_model_name=huggingface/all-MiniLM-L6-v2|' "$A0_ENV"
    else
        echo "A0_SET_embed_model_name=huggingface/all-MiniLM-L6-v2" >> "$A0_ENV"
    fi
    echo -e "${GREEN}✓${NC} Embeddings set to local (huggingface/all-MiniLM-L6-v2 — FREE)"

    # Clean old FAISS index (incompatible with new embedding dimensions)
    rm -rf "$AGENT_ZERO_DIR/usr/memory/" 2>/dev/null
    echo -e "${GREEN}✓${NC} Cleared old FAISS memory (will be recreated with new model)"
else
    echo -e "${YELLOW}⚠${NC} Agent Zero .env not found at $A0_ENV"
    echo "  Creating $A0_ENV with local embedding config..."
    mkdir -p "$(dirname "$A0_ENV")"
    cat > "$A0_ENV" <<'ENVEOF'
A0_SET_embed_model_provider=huggingface
A0_SET_embed_model_name=huggingface/all-MiniLM-L6-v2
ENVEOF
    echo -e "${GREEN}✓${NC} Created $A0_ENV with local embedding config"
fi

# ---------- 6. Install verification + monitoring scripts ----------
echo "--- Step 6: Installing scripts ---"
chmod +x "$POLYMARKET_DIR/scripts/verify_claude_work.sh"
chmod +x "$POLYMARKET_DIR/scripts/watchlist_monitor.sh"
chmod +x "$POLYMARKET_DIR/scripts/setup_a0_memory.sh"
echo -e "${GREEN}✓${NC} Scripts made executable"

# ---------- 7. Set up cron for watchlist monitoring (optional) ----------
echo "--- Step 7: Watchlist monitor cron (optional) ---"
CRON_LINE="*/15 * * * * bash $POLYMARKET_DIR/scripts/watchlist_monitor.sh >> $POLYMARKET_DIR/data/watchlist_cron.log 2>&1"
if crontab -l 2>/dev/null | grep -q "watchlist_monitor"; then
    echo -e "${YELLOW}⚠${NC} Watchlist cron already exists — skipping"
else
    echo "To enable automatic watchlist monitoring every 15 minutes, run:"
    echo "  (crontab -l 2>/dev/null; echo '$CRON_LINE') | crontab -"
    echo "  (Not auto-enabled — user chose 'only when I ask' for scanning)"
fi

# ---------- Verify installation ----------
echo ""
echo "--- Verification ---"
INSTALLED=0

if [ -f "$AGENT_ZERO_DIR/python/tools/claude_code_cli.py" ]; then
    echo -e "${GREEN}✓${NC} Enhanced tool file installed"
    INSTALLED=$((INSTALLED + 1))
else
    echo -e "${RED}✗${NC} Tool file NOT found after copy"
fi

if [ -f "$AGENT_ZERO_DIR/prompts/agent.system.tool.claude_code.md" ]; then
    echo -e "${GREEN}✓${NC} Tool prompt installed"
    INSTALLED=$((INSTALLED + 1))
else
    echo -e "${RED}✗${NC} Tool prompt NOT found after copy"
fi

if [ -f "$POLYMARKET_DIR/data/a0_memory.db" ]; then
    echo -e "${GREEN}✓${NC} SQLite memory DB created"
    INSTALLED=$((INSTALLED + 1))
else
    echo -e "${RED}✗${NC} SQLite memory DB NOT found"
fi

echo ""
echo "=========================================="
if [ $INSTALLED -ge 2 ]; then
    echo -e "${GREEN}✅ Enhanced A0-Claude Pipeline v2 installed!${NC}"
    echo ""
    echo "WHAT'S NEW:"
    echo "  • Auto-approve for low-risk tasks (read, test, analysis)"
    echo "  • Dynamic timeouts (5min/10min/15min by task type)"
    echo "  • 5 Claude calls per session (up from 3)"
    echo "  • Workflow chains (full_trading_pipeline, code_and_verify)"
    echo "  • SQLite + Redis memory (trade journal, lessons, watchlist)"
    echo "  • Daily journal auto-generation"
    echo "  • Morning briefing on login"
    echo "  • Enhanced verification (security scan + performance check)"
    echo "  • Watchlist with webhook alerts"
    echo "  • Local embeddings (FREE — no OpenAI needed)"
    echo ""
    echo "NEXT STEPS:"
    echo "  1. Restart Agent Zero: sudo systemctl restart agent-zero"
    echo "  2. Test: open http://13.50.115.230:5000 and ask A0 to run a health check"
    echo "  3. Try a workflow: 'scan for trading opportunities'"
else
    echo -e "${RED}❌ Installation incomplete — check errors above.${NC}"
    exit 1
fi
