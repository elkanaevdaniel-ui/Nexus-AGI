#!/usr/bin/env bash
# Start all Nexus-AGI services
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Load env
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

echo "=== Nexus-AGI Platform Startup ==="

# Start Claude Code Adapter
echo "[1/2] Starting Claude Code Adapter on port ${CLAUDE_ADAPTER_PORT:-8090}..."
cd "$SCRIPT_DIR/services/claude-adapter"
pip install -q -r requirements.txt 2>/dev/null
nohup uvicorn main:app \
    --host "${CLAUDE_ADAPTER_HOST:-0.0.0.0}" \
    --port "${CLAUDE_ADAPTER_PORT:-8090}" \
    --workers 1 --log-level info > /tmp/claude-adapter.log 2>&1 &
echo "  PID: $!"

# Start Agent Zero (primary UI)
echo "[2/2] Starting Agent Zero UI on port ${WEB_UI_PORT:-50001}..."
cd "$SCRIPT_DIR/agent-zero"
pip install -q -r requirements.txt 2>/dev/null
nohup python run_ui.py > /tmp/agent-zero.log 2>&1 &
echo "  PID: $!"

echo ""
echo "=== All services started ==="
echo "Agent Zero UI: http://localhost:${WEB_UI_PORT:-50001}"
echo "Claude Adapter: http://localhost:${CLAUDE_ADAPTER_PORT:-8090}"
echo ""
echo "Logs:"
echo "  Agent Zero:     tail -f /tmp/agent-zero.log"
echo "  Claude Adapter: tail -f /tmp/claude-adapter.log"
