---
name: nexus-project-manager
description: >
  Manage, improve, and deploy the Nexus-AGI project - a unified AI platform integrating
  Polymarket trading, LinkedIn content automation, lead generation, and Claude Code
  development through Agent Zero. Use this skill whenever working on any aspect of the
  Nexus-AGI project. Trigger on mentions of "Nexus", "Nexus-AGI", "the trading bot",
  "LinkedIn bot", "lead gen", "Agent Zero", or any of the project's services.
---

# Nexus-AGI Project Manager

## Project Overview

| Module | Port | Purpose |
|--------|------|---------|
| Agent Zero | 50001 | Primary UI shell (Flask + Alpine.js + WebSocket) |
| LLM Router | 5100 | Unified multi-provider routing (3-tier: fast/balanced/deep) |
| Cost Tracker | 5200 | Budget management with daily/monthly/session limits |
| Claude Adapter | 5300 | FastAPI wrapper for Claude CLI with SSE streaming |
| LinkedIn Bot | 7860 | Telegram-controlled AI content writer + publisher |
| Trading | 8000 | Polymarket prediction market trading with consensus |
| Lead Gen | 3000/3001 | Apollo.io + Claude AI SDR pipeline (Go + Next.js) |

## Architecture Rules (from CLAUDE.md)

1. **Async-first**: Never use requests library. Always use httpx with async.
2. **No hardcoded secrets**: All secrets go in root .env only.
3. **EC2 rules**: Never expose direct ports. All traffic through Caddy reverse proxy.
4. **Image generation**: NO text in generated images (Imagen can't render text well).
5. **Error handling**: Always wrap external API calls in try/except with proper logging.
6. **Type hints**: Use Python type hints everywhere. Pydantic for data models.

## Known Critical Issues

### CRIT-1: SQL Injection in linkedin-bot/database.py (FIXED)
Added POSTS_ALLOWED_COLUMNS whitelist in update_post().

### CRIT-2: Placeholder Consensus in trading/src/agents/consensus.py (FIXED)
Replaced placeholder returns with real LLM calls via unified router.

### HIGH-1: Duplicate LLM Routing (TODO)
linkedin-bot/smart_router.py duplicates services/llm-router/router.py.
Fix: Replace with HTTP calls to the unified router service.

### HIGH-2: Sync Requests in LinkedIn Bot (TODO)
Multiple files use sync requests instead of async httpx.
Files: smart_router.py, scraper.py, image_gen.py, ai_writer.py

### HIGH-3: No Caching in LLM Router (FIXED)
Added TTL-based LRU cache (cache.py) for identical prompts.

### HIGH-4: Caddyfile Missing Security (FIXED)
Added security headers, health checks, HSTS, CSP.

## Deployment

- **EC2 IP**: 13.50.115.230
- **Domain**: nexus-elkana.duckdns.org
- **Reverse Proxy**: Caddy (auto-HTTPS)
- **Services**: systemd units (nexus-bot, nexus-dashboard, etc.)

## GitHub

- **Owner**: elkanaevdaniel-ui
- **Repo**: Nexus-AGI
- **Branch**: main

