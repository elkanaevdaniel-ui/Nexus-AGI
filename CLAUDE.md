# Nexus-AGI — Claude Code Instructions

## Project Overview
Unified AI platform with Agent Zero as primary UI shell. Integrates autonomous trading (Polymarket), LinkedIn content automation, lead generation, and Claude Code development — all from a single conversational interface.

## Architecture
```
Nexus-AGI/
├── agent-zero/          # Primary UI (Flask + Alpine.js + WebSocket)
│   ├── python/tools/    # Custom tools: claude_code, linkedin, trading, lead_gen, dashboard
│   ├── python/extensions/ # Voice I/O (ElevenLabs STT/TTS)
│   └── webui/           # Web interface + Nexus dashboard panel
├── services/
│   ├── claude-adapter/  # Claude Code CLI → HTTP adapter (FastAPI)
│   ├── llm-router/      # Unified LLM routing (3-tier: fast/balanced/deep)
│   └── cost-tracker/    # Unified budget tracking (daily/monthly/per-run)
├── linkedin-bot/        # Telegram bot + AI writer + image/video gen
├── lead-gen/            # Lead generation pipeline
├── trading/             # Polymarket trading (multi-LLM consensus)
└── cloud/               # Deployment configs (Caddy, systemd)
```

- **Backend**: Python 3.11+, FastAPI, async-first
- **UI**: Agent Zero (Flask + Alpine.js + WebSocket)
- **Database**: SQLite (dev), PostgreSQL (prod), Redis (cache/queue)
- **LLM Providers**: Anthropic, OpenRouter, Gemini, DeepSeek via unified router
- **Deployment**: EC2, systemd services, Caddy reverse proxy

## Code Style
- Python: snake_case, type hints on all public functions, Pydantic models for data
- TypeScript: strict mode, no `any`, prefer `interface` over `type` for objects
- Use 2-space indentation for TS/JSON, 4-space for Python
- Async-first: prefer `async/await` over sync calls for I/O

## Key Conventions
- All API routes return Pydantic models, never raw dicts
- Environment config flows from root `.env` — never hardcode secrets
- Use SQLAlchemy async sessions, not sync
- FastAPI dependency injection for DB sessions and auth
- Next.js: use server components by default, `"use client"` only when needed

## Testing
- Trading: `cd trading && pytest`
- LinkedIn bot: `cd linkedin-bot && pytest` (if tests exist)
- Services: each service has its own test suite
- Always run tests before marking work complete

## Common Mistakes to Avoid
- Do NOT import from `langchain` — use `langchain_core` or `langgraph` directly
- Do NOT use `requests` — use `httpx` with async
- Do NOT create new `.env` files per service — use root `.env`
- Do NOT skip type hints on Python function signatures
- Do NOT use default exports in TypeScript — use named exports
- Do NOT ask the user for API keys — they are ALL stored in `env-restore.b64` and auto-restored
- Do NOT assume API 403 from sandbox = bad key — the sandbox proxy blocks outbound calls
- Do NOT try to test external APIs from Claude Code — test only on EC2
- Do NOT use a single LLM model name — ALWAYS use a fallback chain (e.g., gemini-2.5-flash → gemini-1.5-flash → gemini-1.5-pro)
- Do NOT generate images/video when LLM post generation fails — skip media entirely on placeholder content
- Do NOT forget to tell user to restart the bot on EC2 after pushing code changes
- Do NOT use `pkill` alone to restart the bot — old processes from other venvs/locations may survive. Use `restart.sh`
- Do NOT start a new bot instance without first killing ALL bot processes AND waiting 15s for Telegram poll release
- Do NOT use `logging.getLogger()` for startup diagnostics in modules that load before `logging.basicConfig()` — use `print()` instead
- Do NOT assume `pkill -f "python run.py"` kills everything — check `ps aux | grep -E "run.py|bot.py"` for ghost processes from other paths
- Do NOT restart without checking for processes at `/home/ubuntu/nexus-venv/` and other old venv paths — they hold Telegram poll locks
- Do NOT kill bot processes without FIRST stopping PM2 (`pm2 stop nexus-bot && pm2 kill`) and systemd (`systemctl stop nexus-bot.service`) — they respawn instantly
- Do NOT assume `pkill` alone works — check `ps -ef` for the PPID. If parent is PM2 God Daemon or systemd, stop the MANAGER first

## API Keys & Config — NEVER Ask, Always Use What Exists
- **ALL keys are already in the project** — stored in `.claude/hooks/env-restore.b64` (base64 encoded, committed to git)
- **SessionStart hook** auto-restores `.env` from this backup every session — keys are ALWAYS available
- **NEVER ask the user for API keys, tokens, or credentials** — they are permanently stored and auto-restored
- **NEVER say "key is missing"** without first checking: (1) `.env` file, (2) `env-restore.b64` backup, (3) `known-config.md`
- **If an API call fails**: The key EXISTS in the project. Debug the actual error (expired key, wrong model, API down) — do NOT blame missing keys
- **If a key needs updating**: User provides new value → update `.env` → regenerate `env-restore.b64` → commit. Done forever.
- **Persistent memory**: `.claude/knowledge/known-config.md` tracks all key locations and statuses
- **On session start**: Read `known-config.md` silently — every key marked CONFIGURED is permanent
- **Do NOT run `/env-check` automatically** — only when the user explicitly asks
- **EC2 deployment**: After updating keys, ALWAYS remind user to pull on EC2 and decode `env-restore.b64` into EC2's `.env`
- **The encoded backup is the SINGLE SOURCE OF TRUTH** — if `.env` doesn't exist, decode from `env-restore.b64`

### Key Update Procedure (when user provides a new key)
1. Update the key in `.env`
2. Run: `grep -v '^#' .env | grep -v '^$' | base64 -w0 > .claude/hooks/env-restore.b64`
3. Update `known-config.md` with the change date
4. Commit both files
5. Tell user to pull on EC2 and run: `cat .claude/hooks/env-restore.b64 | base64 -d > .env`

## PR Guidelines
- Keep PRs under 400 lines when possible
- Title format: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`
- Always include a test plan in PR description

## EC2 Environment Rules
- This project runs on AWS EC2 — NEVER refer to `localhost` or `127.0.0.1` when giving the user URLs
- Server IP: `13.50.115.230` | Domain: `nexus-elkana.duckdns.org`
- **ALL services are behind Caddy reverse proxy** — ALWAYS use the Caddy proxy URLs (port 80/443), NEVER direct port URLs
- Direct port access (e.g., `http://13.50.115.230:3001`) is blocked by the OS firewall (ufw only allows 22, 80, 443)
- Caddy auto-manages HTTPS via Let's Encrypt on the DuckDNS domain

### Service URLs (use these — they work)
| Service | URL |
|---------|-----|
| Lead Gen Frontend | `https://nexus-elkana.duckdns.org/leadgen` |
| Lead Gen API | `https://nexus-elkana.duckdns.org/leadgen/api/` |
| Dashboard | `https://nexus-elkana.duckdns.org/dashboard` |
| Command Center API | `https://nexus-elkana.duckdns.org/api/` |
| Main Landing | `https://nexus-elkana.duckdns.org/` |

### Internal ports (localhost only — for Caddy proxy, NOT for user-facing URLs)
- Lead Gen Frontend: `localhost:3001` | Lead Gen API: `localhost:8082`
- Dashboard: `localhost:3000` | Command Center API: `localhost:8080`

### Networking Rules
- NEVER give the user `http://13.50.115.230:<port>` URLs — they will NOT work (ufw blocks them)
- NEVER open individual service ports in ufw — always route through Caddy
- If a service is unreachable, check: (1) Caddy is running, (2) Caddyfile has the route, (3) backend is listening on localhost
- Caddyfile source of truth: `cloud/Caddyfile` — deploy with `sudo cp` + `sed` domain replacement + `systemctl reload caddy`

## READ BEFORE ACTING — Mandatory Rule
- **ALWAYS read the user's ENTIRE message before taking ANY action**
- Do NOT start executing after reading the first sentence — read everything first
- If the message contains multiple instructions, parse ALL of them before starting work
- Plan your approach based on the COMPLETE message, not partial understanding
- This rule applies to EVERY session, EVERY message, no exceptions

## Message Understanding & Skill Discovery — Every Message
On EVERY user message, before executing:
1. **Parse intent**: What does the user actually want? Break into sub-tasks
2. **Check existing skills**: Does `/toolkit` have a skill that handles this? Use it
3. **Spot skill gaps**: If no skill exists and this feels like a repeatable task, suggest: "I could create a `/skill-name` skill for this — want me to?"
4. **Only create after approval** — suggest first, create only if the user agrees
5. **Search before building**: Use `/find-skills` mentally to check if community skills exist
- This makes me smarter every session — the skill library grows with usage

## Proactive Agent Usage — Mandatory After Code Changes
Agents MUST be used automatically in these situations:
- **After writing/editing code**: Run `verify-app` to catch import errors, type issues, broken tests
- **Before committing**: Run `staff-reviewer` to catch issues before they ship
- **After implementing features**: Run `test-writer` if no tests exist for the new code
- **When code gets complex**: Run `code-simplifier` to reduce complexity
- **When debugging errors**: Run `debugger` agent instead of guessing
- **When planning big changes**: Run `code-architect` for design review
- **For production issues**: Run `oncall-guide` for systematic triage
- These are NOT optional — skipping agents leads to bugs, regressions, and wasted time
- Run agents in **parallel** when possible (e.g., `verify-app` + `staff-reviewer` together)
- Run agents in **background** when the user doesn't need to wait for results

## Session Startup
- At the start of every new chat: show quick 3-line status (current branch, last commit, pending issues)
- Silently read `.claude/knowledge/known-config.md` to load persistent config memory — do NOT print or discuss it
- Then wait for instructions — don't auto-run commands
- Always check for uncommitted changes before starting new work
- Read this CLAUDE.md first to load project context and rules

## Environment Auto-Restore
- **Keys are stored encoded** in `.claude/hooks/env-restore.b64` (base64, committed to git)
- **SessionStart hook** (`.claude/hooks/setup-env.sh`) automatically decodes and creates `.env` every session
- **NEVER ask the user for API keys** — they are permanently stored in the encoded backup
- If a key needs to change: update `.env`, then run `grep -v '^#' .env | grep -v '^$' | base64 -w0 > .claude/hooks/env-restore.b64` and commit
- The encoded backup is the **single source of truth** for key values across all sessions

## Claude Code Sandbox Limitations
- **Claude Code runs in a sandboxed container** — NOT on EC2. It has a proxy that blocks most outbound API calls
- **You CANNOT test APIs from this sandbox** — calls to OpenRouter, Gemini, OpenAI, Telegram etc. will all get 403/blocked
- **You CAN**: edit code, commit, push to GitHub. The user then pulls and runs on EC2
- **You CANNOT**: start the bot, call external APIs, test endpoints, SSH to EC2
- **Never confuse sandbox failures with real API issues** — if an API returns 403 from here, it's the sandbox proxy, not the key
- **Workflow**: Edit code here → commit & push → user pulls on EC2 → user restarts services → user tests on Telegram
- **EC2 has direct internet** — no proxy, no sandbox, no docker. That's the production environment

## Image Generation Rules
- NEVER generate images with text, words, letters, or labels baked in
- Images must be pure visual storytelling — cinematic, bold, movie-poster quality
- Always detect scene type from post topic keywords (see `linkedin-bot/image_gen.py` `_detect_scene()`)
- Enforce NO-TEXT rule with explicit negative instructions in every image prompt
- `linkedin-bot/image_gen.py` is the GOLD STANDARD for image generation — never diverge from its approach
- Pillow fallback should be atmospheric/abstract (gradients, glow orbs, particles, silhouettes) — NO text rendering

## Session-End Learning — Mandatory Auto-Review
- **At the END of every session**, before wrapping up, AUTOMATICALLY:
  1. Review the ENTIRE session conversation — every message, every error, every fix
  2. Extract lessons learned (problems, root causes, fixes, prevention rules)
  3. Categorize each lesson with severity: CRITICAL / HIGH / MEDIUM / LOW
  4. Update `.claude/knowledge/guidebook.md` → "Lessons Learned" section with full incident logs
  5. Add CRITICAL/HIGH rules directly to this CLAUDE.md → "Common Mistakes to Avoid"
  6. Also capture "wins" — successful patterns and approaches worth repeating
- **Format per lesson**: Problem → Root Cause → Fix → Prevention Rule → Severity
- **Categories**: Bot Management, API Keys, Deployment/EC2, Git/Code, LLM/AI, Frontend, Database, Config
- **This is NOT optional** — every session must end with learning extraction
- **Goal**: Never encounter the same issue twice. If we fixed it once, the prevention rule prevents it forever

## EC2 Bot Restart — Safe Procedure
- **NEVER just `pkill -f "python run.py"`** — there may be OTHER bot processes (old venvs, systemd, cron)
- **ALWAYS use the safe restart script**: `bash ~/ai-projects/linkedin-bot/restart.sh`
- The restart script: (1) kills ALL python bot/run processes, (2) waits 15s for Telegram poll release, (3) starts single clean instance
- **After pushing code changes**, ALWAYS tell the user: `cd ~/ai-projects && git pull origin <branch> && bash linkedin-bot/restart.sh`
- **NEVER start the bot while another instance may be running** — always kill first, verify clean, wait, then start

## LinkedIn Post Rules
- Posts must be 120-180 words max (shorter = more engagement on LinkedIn)
- Structure: hook (max 12 words) → insight bullets → urgency close → CTA question
- Rotate CTA types: debate questions, experience sharing, tag & share, action prompts
- Rotate frameworks: PAS (Problem-Agitate-Solve), AIDA (Attention-Interest-Desire-Action), Contrarian hook + proof
- Hashtags: 3-5 at end for discoverability
- Sources: separate numbered list with titles below post (not in post body)
- No walls of text — short punchy lines and bullet points only
