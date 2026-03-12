#!/usr/bin/env bash
# Start all services: Redis + Polymarket Agent + Agent Zero
set -euo pipefail

echo "=== Starting All Services ==="

# 1. Redis
echo "[1/3] Starting Redis..."
sudo systemctl start redis-server 2>/dev/null || sudo systemctl start redis 2>/dev/null || echo "  Redis may already be running"

# 2. Polymarket Agent
echo "[2/3] Starting Polymarket Agent..."
sudo systemctl start polymarket-agent

# 3. Agent Zero
echo "[3/3] Starting Agent Zero..."
sudo systemctl start agent-zero

# Wait for services to stabilize
sleep 3

echo ""
echo "=== Service Status ==="
echo "Redis:              $(systemctl is-active redis-server 2>/dev/null || systemctl is-active redis 2>/dev/null || echo 'unknown')"
echo "Polymarket Agent:   $(systemctl is-active polymarket-agent 2>/dev/null || echo 'unknown')"
echo "Agent Zero:         $(systemctl is-active agent-zero 2>/dev/null || echo 'unknown')"
echo ""
echo "Dashboard:          http://localhost:8000"
echo "Agent Zero UI:      http://localhost:50001"
echo ""

# Health check
echo "=== Health Check ==="
curl -s http://localhost:8000/health 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "Polymarket Agent: not responding yet (may still be starting)"
