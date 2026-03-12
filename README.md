# Nexus-AGI

Unified AI platform with Agent Zero as the primary UI shell, integrating autonomous trading (Polymarket), LinkedIn content automation, lead generation, and Claude Code-powered development — all controlled from a single conversational interface.

## Architecture

```
Nexus-AGI/
├── agent-zero/          # Primary UI shell (Flask + Alpine.js + WebSocket)
│   ├── python/tools/    # Custom tools: claude_code, linkedin, trading, lead_gen, dashboard
│   ├── python/extensions/ # Voice I/O (ElevenLabs STT/TTS)
│   ├── python/api/      # Nexus health API
│   └── webui/           # Agent Zero web interface + Nexus dashboard panel
├── services/
│   ├── claude-adapter/  # Claude Code CLI → HTTP adapter (FastAPI)
│   ├── llm-router/      # Unified LLM routing (replaces 5 duplicate routers)
│   └── cost-tracker/    # Unified budget tracking (replaces 3 duplicate trackers)
├── linkedin-bot/        # Telegram bot + AI writer + image/video gen
├── lead-gen/            # Lead generation pipeline
├── trading/             # Polymarket trading agent (multi-LLM consensus)
├── cloud/               # Deployment configs (Caddy, systemd)
└── docs/                # Architecture documentation
```

## Quick Start

```bash
cp .env.example .env     # Configure your API keys
cd agent-zero && pip install -r requirements.txt
python run_ui.py         # Starts Agent Zero on port 50001
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| Agent Zero UI | 50001 | Primary shell — chat, voice, dashboard |
| Claude Adapter | 8090 | Routes coding tasks to Claude Code CLI |
| LinkedIn Bot | 8083 | Telegram bot + A0 tool for LinkedIn posting |
| Lead Gen API | 8082 | Lead generation pipeline |
| Trading Agent | 8000 | Polymarket trading with multi-LLM consensus |

## Key Features

- **Single UI**: Agent Zero handles all interactions — no separate dashboards
- **Voice I/O**: ElevenLabs STT/TTS for hands-free operation
- **Unified LLM Router**: 3-tier routing (fast/balanced/deep) with fallback chains
- **Budget Control**: Unified cost tracking with daily/monthly/per-run limits
- **Nexus Dashboard**: Sidebar widget showing all service health + quick actions
- **Claude Code Integration**: Route coding tasks through Claude Code adapter
- **Multi-LLM Trading**: Weighted consensus from Claude + Gemini + GPT for probability estimation
