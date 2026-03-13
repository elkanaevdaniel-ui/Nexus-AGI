# CLAUDE.md — Nexus-AGI Master Rules

> Auto-updated compounding ruleset. Every correction becomes a permanent rule.
> After every fix, append: "Update CLAUDE.md so you don't make that mistake again."

---

## Tip 1: Parallelization

- When facing multi-module work, spin up separate contexts per module
- Use subagents for independent tasks (reading files, running tests, researching)
- Never let one task's context contaminate another — isolate trading work from linkedin-bot work from lead-gen work
- For analysis tasks (reading logs, running queries), use a dedicated read-only context that doesn't modify files

## Tip 2: Re-plan When Stuck

- If something fails twice, STOP. Switch to Plan Mode immediately
- Re-plan includes verification steps, not just implementation steps
- Before executing any plan, review it adversarially: "What could go wrong? What edge cases am I missing?"
- When a plan involves financial code (trading module), spin up a second review pass as a "staff engineer" before committing
- Never keep pushing on a failing approach — re-plan with the new information

## Tip 3: Self-Updating Rules

- After EVERY correction or bug fix, add a rule here preventing the same mistake
- Rules compound — this file should grow over time as the project matures
- Format: LEARNED [date]: [what happened] → [rule to prevent it]

### Learned Rules
LEARNED 2026-03-13: SQL injection via f-string column names → Always whitelist column names before interpolating into SQL
LEARNED 2026-03-13: Placeholder LLM code shipped to main → Never merge placeholder/stub code without a TODO issue
LEARNED 2026-03-13: Duplicate routing systems diverged → Single source of truth for LLM routing
LEARNED 2026-03-13: sync requests used when CLAUDE.md says httpx → Run grep -r "import requests" before every commit
LEARNED 2026-03-13: Agent Zero LiteLLM 404 → Check LLM provider health endpoints before declaring operational

## Tip 4: Skills as Institutional Knowledge

- If you do something more than once, create a skill for it
- Skills live in .claude/skills/ and are checked into git
- Required skills: /techdebt, /verify, /review, /context-dump, /deploy

## Tip 5: Self-Fixing Bugs

- When given a bug report, fix it directly — don't ask for permission
- Point at logs first: journalctl -u nexus-bot --since "1 hour ago"
- After fixing, verify via health endpoint or running relevant test

## Tip 6: Prompting as Provocation

- After mediocre fix: "Scrap this and implement the elegant solution"
- Before any PR: "Grill me on these changes — don't merge until code passes review"
- Challenge every plan — treat Claude as a peer, not an assistant

## Tip 7: Terminal & Environment Setup

- Always show context usage and git branch in status line
- Color-code tabs by module: trading=red, linkedin=blue, lead-gen=green, infra=yellow
- Keep separate terminal tabs per worktree/task for context isolation

## Tip 8: Subagents for Context Hygiene

- Append "Use subagents" to any request where more compute helps
- Offload tasks to subagents to keep main context clean
- Use subagents for: file reading, test running, log analysis, web research

## Tip 9: Claude Replaces SQL

- Never write raw SQL manually — describe the need and let Claude generate + run it
- Always parameterize queries — NEVER interpolate user input into SQL strings

## Tip 10: Learning Mode

- Ask for ASCII diagrams of architecture when exploring unfamiliar code
- Generate HTML presentations to explain complex modules
- Document learnings in per-module README files

---

## Project-Specific Rules (Non-Negotiable)

### Architecture
- Async-first everywhere. Never use requests. Always use httpx with async
- All LLM calls go through the unified router at services/llm-router/ (port 5100)
- No hardcoded secrets. Everything in root .env with NEXUS_ prefix
- Pydantic models for all data structures. Type hints on every function

### EC2 Deployment
- Never expose direct ports. All traffic through Caddy reverse proxy
- Domain: nexus-elkana.duckdns.org | IP: 13.50.115.230
- Services managed via systemd
- After every deploy: curl -s https://nexus-elkana.duckdns.org/health to verify

### LinkedIn Bot
- NO text in AI-generated images
- Daily style rotation for images (7 styles, one per weekday)
- Column whitelist in database.py — NEVER interpolate unvalidated column names

### Trading
- Paper broker for testing. NEVER send live orders without human approval via Telegram
- Kelly criterion with fee adjustment for position sizing
- Circuit breakers: daily loss limit, drawdown limit, auto-reset at UTC midnight
- Multi-LLM consensus via unified router — minimum 2/3 agreement before any trade signal

### Cost Management
- Budget limits enforced via cost-tracker service (port 5200)
- Daily, monthly, per-run, and per-session limits using Decimal arithmetic
- Check budget BEFORE making LLM calls, not after
