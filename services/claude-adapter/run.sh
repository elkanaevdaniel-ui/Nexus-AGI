#!/usr/bin/env bash
# Start the Claude Code Adapter Service
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Load env from project root if available
ROOT_ENV="$(dirname "$(dirname "$SCRIPT_DIR")")/.env"
if [ -f "$ROOT_ENV" ]; then
    set -a
    source "$ROOT_ENV"
    set +a
fi

exec uvicorn main:app \
    --host "${CLAUDE_ADAPTER_HOST:-0.0.0.0}" \
    --port "${CLAUDE_ADAPTER_PORT:-8090}" \
    --workers 1 \
    --log-level info
