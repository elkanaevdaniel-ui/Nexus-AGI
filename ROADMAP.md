# Nexus AGI — Project Roadmap

## Architecture
```
Agent Zero (LiteLLM) → Claude Adapter (:8090) → Claude CLI → Anthropic API
```
EC2 Instance: i-07313a6559bd589be (eu-north-1) | IP: 13.50.115.230
Git Repo: github.com/elkanaevdaniel-ui/Nexus-AGI

---

## Current Capabilities

### 💬 Conversational AI
Agent Zero with multi-model routing via Claude Adapter. Sonnet 4.6 for fast responses.

### 📊 Trading
Polymarket paper trading with 3-LLM consensus + Kelly criterion sizing.

### 📝 LinkedIn Automation
AI content writing + image generation + Telegram bot interface.

### 🎯 Lead Generation
Apollo-powered lead pipeline with scoring.

### 🌐 Web Browsing
Playwright-based browser automation.

### 🔍 Research
DuckDuckGo search + document analysis.

### 📅 Task Scheduling
Cron/planned/adhoc task execution.

### 🗣️ Voice
Whisper STT + Kokoro TTS.

### 🔧 Code Execution
Terminal, Python, Node.js sandboxed execution.

### 🧠 Memory
FAISS vector memory with semantic search.

---

## Roadmap Phases

### Phase 1 — Done ✅
- Monorepo setup and project structure
- CLAUDE.md rules and skill definitions
- Claude Code Adapter (FastAPI on port 8090)
- Git hooks and CI scaffolding
- Agent Zero integration with Claude
- Embedding model (sentence-transformers/all-MiniLM-L6-v2)

### Phase 2 — In Progress 🔨
- Service stabilization and error handling
- API key configuration and auth flow cleanup
- Response speed optimization (Sonnet, max_turns=1)
- Agent Zero UI fixes (Alpine.js state sync)
- Cost tracking and budget enforcement

### Phase 3 — Planned 📋
- Twilio voice integration (STT/TTS pipeline)
- Binance crypto trading (live market data)
- LangSmith tracing for debugging LLM calls
- Dashboard polish and monitoring
- Multi-client session isolation

### Phase 4 — Future 🔮
- Live trading (move from paper to real)
- Multi-client isolation (per-user sessions)
- Dashboard with real-time metrics
- Advanced memory (long-term knowledge graphs)
- Plugin marketplace for Agent Zero tools

---

## Budget & Cost Limits

| Budget     | Limit        |
|------------|-------------|
| Daily      | $5.00       |
| Monthly    | $20.00      |
| Per-run    | $1.00       |
| Sessions   | Max 10 calls/session |

**Cost Stack:**
- Claude (Anthropic API) — primary LLM cost via Claude CLI
- 11 Labs — voice synthesis (planned)
- Gemini — secondary model for classification/routing (planned)

**Cost Controls:**
- LLM Router has LRU cache (500 entries, 300s TTL)
- Cost tracker service at port 5200 (Decimal arithmetic)
- Max turns per request: 1 (enforced in adapter)

---

## Services

| Service         | Port  | Status    |
|-----------------|-------|-----------|
| Agent Zero UI   | 50001 | Running   |
| Claude Adapter  | 8090  | Running   |
| Cost Tracker    | 5200  | Planned   |
| LLM Router      | 5100  | Planned   |
| Caddy (reverse) | 80/443| Planned   |

---

*Last updated: March 14, 2026*
