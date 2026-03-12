#!/bin/bash
# Safe restart script for the Polymarket Trading Agent.
# After restart, live mode starts PAUSED — manual confirmation required.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Polymarket Agent Restart ==="
echo "Project: $PROJECT_DIR"

# Stop existing process gracefully
if systemctl is-active --quiet polymarket-agent 2>/dev/null; then
    echo "Stopping existing service..."
    sudo systemctl stop polymarket-agent
    sleep 2
fi

# Run the agent
echo "Starting agent..."
cd "$PROJECT_DIR"
python run.py &

echo "Agent started. PID: $!"
echo "NOTE: If LIVE mode, trading is PAUSED until manual confirmation."
