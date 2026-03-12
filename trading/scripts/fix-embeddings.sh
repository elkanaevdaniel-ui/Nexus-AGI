#!/usr/bin/env bash
# ==============================================================================
# fix-embeddings.sh
# Quick fix for OpenAI embedding quota error in Agent Zero
# Installs sentence-transformers locally and configures litellm to use it
# ==============================================================================
# Run: bash ~/polymarket-agent/scripts/fix-embeddings.sh
# Then: sudo systemctl restart agent-zero
# ==============================================================================

set -uo pipefail

AGENT_ZERO_DIR="${AGENT_ZERO_DIR:-/home/ubuntu/agent-zero}"
A0_ENV="$AGENT_ZERO_DIR/usr/.env"
A0_VENV="$AGENT_ZERO_DIR/venv"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=== Fixing Agent Zero Embeddings ==="
echo ""

# Step 1: Install sentence-transformers
echo "--- Installing sentence-transformers ---"
if [ -d "$A0_VENV" ]; then
    "$A0_VENV/bin/pip" install sentence-transformers 2>&1 | tail -3
    if "$A0_VENV/bin/python" -c "import sentence_transformers; print(f'  Version: {sentence_transformers.__version__}')" 2>/dev/null; then
        echo -e "${GREEN}✓${NC} sentence-transformers ready"
    else
        echo -e "${RED}✗${NC} Failed to install sentence-transformers"
        exit 1
    fi
else
    echo -e "${RED}✗${NC} Agent Zero venv not found at $A0_VENV"
    exit 1
fi

# Step 2: Pre-download the model so first startup is fast
echo ""
echo "--- Pre-downloading all-MiniLM-L6-v2 model ---"
"$A0_VENV/bin/python" -c "
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')
result = model.encode(['test'])
print(f'  Model loaded, embedding dimension: {len(result[0])}')
" 2>/dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} Model downloaded and verified"
else
    echo -e "${YELLOW}⚠${NC} Model download may have failed — will auto-download on first use"
fi

# Step 3: Update .env config
echo ""
echo "--- Updating embedding config ---"
if [ -f "$A0_ENV" ]; then
    # Set provider
    if grep -q "A0_SET_embed_model_provider" "$A0_ENV"; then
        sed -i 's/A0_SET_embed_model_provider=.*/A0_SET_embed_model_provider=huggingface/' "$A0_ENV"
    else
        echo "A0_SET_embed_model_provider=huggingface" >> "$A0_ENV"
    fi
    # Set model name with huggingface/ prefix for litellm routing
    if grep -q "A0_SET_embed_model_name" "$A0_ENV"; then
        sed -i 's|A0_SET_embed_model_name=.*|A0_SET_embed_model_name=huggingface/all-MiniLM-L6-v2|' "$A0_ENV"
    else
        echo "A0_SET_embed_model_name=huggingface/all-MiniLM-L6-v2" >> "$A0_ENV"
    fi
    echo -e "${GREEN}✓${NC} Updated $A0_ENV"
else
    mkdir -p "$(dirname "$A0_ENV")"
    cat > "$A0_ENV" <<'EOF'
A0_SET_embed_model_provider=huggingface
A0_SET_embed_model_name=huggingface/all-MiniLM-L6-v2
EOF
    echo -e "${GREEN}✓${NC} Created $A0_ENV"
fi

# Step 4: Clear old FAISS index (dimensions won't match)
echo ""
echo "--- Clearing old FAISS index ---"
rm -rf "$AGENT_ZERO_DIR/usr/memory/" 2>/dev/null
echo -e "${GREEN}✓${NC} Old memory index cleared (will rebuild on startup)"

# Step 5: Show current config
echo ""
echo "--- Current embedding config ---"
grep -i embed "$A0_ENV" 2>/dev/null || echo "(none found)"

echo ""
echo "=== Done ==="
echo ""
echo "Next steps:"
echo "  sudo systemctl restart agent-zero"
echo "  sudo systemctl status agent-zero"
echo ""
echo "If it STILL fails with OpenAI errors, Agent Zero may have a hardcoded"
echo "embedding model elsewhere. Check with:"
echo "  grep -rn 'text-embedding' $AGENT_ZERO_DIR/models.py"
echo "  grep -rn 'openai' $AGENT_ZERO_DIR/models.py | grep -i embed"
