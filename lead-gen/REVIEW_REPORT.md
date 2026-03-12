# Lead Gen — Full Project Review Report

**Date:** 2026-03-07
**Reviewers:** 9 AI agents (Deep Research x6, Plan-Review, Multi-Role Review, Adversarial Grill)
**Overall Grade: C+**

---

## Executive Summary

The Lead Gen platform is a well-conceived B2B lead generation tool with a solid product vision: natural language ICP parsing → Apollo.io search → AI scoring → enrichment → outreach draft generation → CRM pipeline. The architecture is clean, the API is RESTful, and the code is organized.

However, it has **3 critical security vulnerabilities**, **2 data corruption bugs**, and **significant architectural violations** of the project's own CLAUDE.md rules that prevent it from being production-ready.

**Minimum viable fix set** (estimated ~4 hours) to reach production safety:
1. Fix auth bypass
2. Fix background task DB session bug
3. Remove API key from client-side JS
4. Add CSV injection protection
5. Restrict CORS
6. Add .gitignore

---

## Table of Contents

1. [Multi-Role Grades](#1-multi-role-grades)
2. [Critical Issues (BLOCK)](#2-critical-issues-block)
3. [High Priority Issues (WARN)](#3-high-priority-issues-warn)
4. [Medium Priority Issues](#4-medium-priority-issues)
5. [Low Priority Issues (NIT)](#5-low-priority-issues-nit)
6. [Security Audit Summary](#6-security-audit-summary)
7. [Architecture Assessment](#7-architecture-assessment)
8. [Phased Implementation Plan](#8-phased-implementation-plan)
9. [Skeptical Review of the Plan](#9-skeptical-review-of-the-plan)
10. [Questions for the Author](#10-questions-for-the-author)

---

## 1. Multi-Role Grades

| Role | Grade | Verdict |
|------|-------|---------|
| **Product Manager** | B- | Complete user journey, but "Send" is fake, no user/team model, no deduplication |
| **Backend Engineer** | B | Clean API design, good retry logic, but sync DB in async app, broken pipeline sessions |
| **Frontend Engineer** | B- | Clean components, strict TypeScript, but no error boundaries, no loading skeletons, no a11y |
| **DevOps Engineer** | D+ | Simple startup script, but no CI/CD for lead-gen, no logging, no monitoring, SQLite in prod |
| **Security Engineer** | D | Auth bypass by default, API key in browser JS, no rate limiting, prompt injection risk |

---

## 2. Critical Issues (BLOCK)

These must be fixed before any production deployment.

### BLOCK-1: Authentication Bypass When API Key Not Configured
- **File:** `src/auth.py:15-16`
- **Impact:** When `COMMAND_CENTER_API_KEY` is empty (the default), ALL requests are allowed through with no authentication
- **Fix:** Fail closed — reject all requests or refuse to start if no API key is configured

### BLOCK-2: API Key Leaked to Browser via `NEXT_PUBLIC_API_KEY`
- **File:** `frontend/src/lib/api.ts:13`
- **Impact:** The `NEXT_PUBLIC_` prefix bundles the API key into client-side JavaScript, visible to anyone in browser DevTools
- **Fix:** Remove `NEXT_PUBLIC_` prefix. Route API calls through the Next.js server-side proxy (`app/api/[...path]/route.ts`) and inject the key server-side only

### BLOCK-3: Background Task Uses Request-Scoped DB Session
- **File:** `src/api/campaigns.py:103-110` and `134-141`
- **Impact:** `asyncio.create_task(run_campaign_pipeline(..., db=db))` passes the request's DB session to a background task. Once the HTTP response returns, `get_db()` closes the session. The pipeline then operates on a dead session — causing crashes or silent data corruption on **every pipeline run**
- **Fix:** Create a new `SessionLocal()` inside `run_campaign_pipeline` instead of passing the request session

### BLOCK-4: Synchronous SQLAlchemy in Async Application
- **File:** `src/database.py:3-17`
- **Impact:** Violates CLAUDE.md ("Use SQLAlchemy async sessions, not sync"). Every `db.query()` blocks the event loop. Under concurrent load, the server stalls
- **Fix:** Migrate to `create_async_engine` + `AsyncSession` from `sqlalchemy.ext.asyncio`

### BLOCK-5: No Cascade Deletes — Orphaned Data
- **File:** `src/models/lead.py:100`
- **Impact:** Deleting a campaign with leads fails with FK constraint error (or orphans data). Same for deleting leads with outreach messages
- **Fix:** Add `cascade="all, delete-orphan"` to `Campaign.leads`, `Lead.outreach_messages`, `Lead.deal` relationships

### BLOCK-6: No Rate Limiting on Any Endpoint
- **File:** `src/main.py` (entire application)
- **Impact:** `slowapi` is in `requirements.txt` but never used. LLM and Apollo endpoints can be spammed to drain paid API credits
- **Fix:** Configure `slowapi` with per-endpoint limits, especially on `/api/leads/search`, `/api/leads/score`, `/api/outreach/generate`

### BLOCK-7: `lead_gen.db` and `__pycache__` in Repository
- **File:** `lead-gen/` (missing `.gitignore`)
- **Impact:** SQLite database with PII (names, emails, phone numbers) and compiled Python files tracked in git
- **Fix:** Create `.gitignore` with `*.db`, `__pycache__/`, `.env`, `.venv/`

### BLOCK-8: CSV Injection in Export
- **File:** `src/services/export_service.py:93-94`
- **Impact:** Lead data written directly to CSV without sanitization. Cells starting with `=`, `+`, `-`, `@` can execute formulas in Excel
- **Fix:** Prefix dangerous cell values with a single quote (`'`)

---

## 3. High Priority Issues (WARN)

### WARN-1: Sequential LLM Calls — Pipeline Takes 2-5 Minutes
- **Files:** `src/scoring/lead_scorer.py:102-112`, `src/outreach/message_generator.py:98-113`
- Both `score_leads_batch` and `generate_batch` process leads sequentially. For 75 leads, that's 150+ sequential API calls
- **Fix:** Use `asyncio.gather` with a semaphore (concurrency=10)

### WARN-2: `httpx.AsyncClient` Created Per Request
- **File:** `src/services/apollo_client.py:45`
- New TCP connection + TLS handshake for every API call. Wastes time and resources
- **Fix:** Hold a persistent client instance with proper lifecycle management

### WARN-3: ICP Parsing Silently Returns Empty Filters
- **File:** `src/services/icp_parser.py:79-80`
- If LLM returns unparseable JSON, returns `ICPFilters()` with all empty lists. Campaign searches with no filters, gets random results
- **Fix:** Log warning, return parse failure indicator to caller

### WARN-4: LLM Prompt Injection via `custom_instructions`
- **File:** `src/outreach/message_generator.py:41`
- User-supplied `custom_instructions` interpolated directly into LLM prompt with no sanitization
- **Fix:** Add length limit, injection detection, and defensive system prompt instructions

### WARN-5: CORS Overly Permissive
- **File:** `src/main.py:33-34`
- `allow_credentials=True` with `allow_methods=["*"]` and `allow_headers=["*"]`
- **Fix:** Whitelist specific methods and headers

### WARN-6: Silent LLM Parse Failures
- **Files:** `src/scoring/lead_scorer.py:95-97`, `src/outreach/message_generator.py:90-95`
- Score defaults to 0, outreach uses raw LLM content — no logging of failures
- **Fix:** Add `logger.warning()` on parse failures

### WARN-7: Campaign Status Not Validated on Update
- **File:** `src/schemas.py:51`
- PATCH endpoint accepts arbitrary status strings. Unlike `bulk_update_status` which validates
- **Fix:** Add `Literal` type constraint to status fields

### WARN-8: `connect_args` Hardcoded for SQLite
- **File:** `src/database.py:15`
- `check_same_thread=False` is SQLite-specific. Will break with PostgreSQL in production
- **Fix:** Conditional config based on URL scheme

---

## 4. Medium Priority Issues

| # | Issue | File | Fix |
|---|-------|------|-----|
| M1 | No database migrations (uses `create_all()`) | `database.py:36` | Add Alembic |
| M2 | Pipeline has no transaction safety | `pipeline.py` | Add per-stage try/except with error tracking |
| M3 | Health endpoint returns raw dict (violates CLAUDE.md) | `main.py:51` | Return Pydantic model, add DB check |
| M4 | `get_pipeline_stats` makes 7 separate COUNT queries | `lead_service.py:117` | Single query with `CASE WHEN` |
| M5 | Missing indexes on `OutreachMessage.campaign_id`, `lead_id`, `CRMDeal.lead_id` | `models/lead.py` | Add `index=True` |
| M6 | Raw Apollo response stored in `raw_data` column | `apollo_client.py:205` | Store only needed fields |
| M7 | No error boundaries in React frontend | `frontend/src/app/` | Add `error.tsx` and `global-error.tsx` |
| M8 | No loading skeletons — bare "Loading..." text | All pages | Add skeleton components |
| M9 | Frontend header forwarding in proxy | `app/api/[...path]/route.ts` | Whitelist headers |
| M10 | Timing attack on API key comparison | `auth.py:17` | Use `hmac.compare_digest()` |
| M11 | Enrichment errors silently swallowed | `lead_service.py:108` | Log exception with lead ID |
| M12 | No test coverage for AI endpoints or pipeline | `tests/` | Add tests for scoring, outreach, pipeline |
| M13 | `langchain-anthropic` missing from `requirements.txt` | `requirements.txt` | Add the dependency |
| M14 | `langgraph` has no version pin (`>=0.4.10`) | `requirements.txt` | Pin to `~=0.4.10` |
| M15 | Export endpoint has no size limit — memory bomb | `export_service.py:83` | Stream rows with generator |
| M16 | Schemas file is monolithic (290 lines) | `schemas.py` | Split into per-domain modules |
| M17 | Content-Disposition header not sanitized | `campaigns.py:204` | Use strict character allowlist |

---

## 5. Low Priority Issues (NIT)

| # | Issue | File |
|---|-------|------|
| N1 | Frontend pages use `export default` (CLAUDE.md violation, but Next.js requires it) | All `page.tsx` |
| N2 | Unused `AIMessage` import | `utils/llm.py:13` |
| N3 | `get_db` missing return type annotation | `database.py:39` |
| N4 | f-string with no placeholder | `lead_scorer.py:97` |
| N5 | Variable `l` used as loop variable (looks like `1`) | `pipeline.py:80` |
| N6 | `EmptyState` uses `<a>` instead of Next.js `<Link>` | `components/EmptyState.tsx:16` |
| N7 | No dark mode support | Frontend |
| N8 | No accessibility (ARIA labels, keyboard nav, screen readers) | All frontend components |
| N9 | Placeholder `.env.example` value looks like real key | `.env.example:8` |
| N10 | No frontend tests | `frontend/` |

---

## 6. Security Audit Summary

| Severity | Count | Key Issues |
|----------|-------|------------|
| **CRITICAL** | 3 | Auth bypass, API key in client JS, weak `.env.example` |
| **HIGH** | 5 | No rate limiting, CORS, CSV injection, prompt injection, no gitignore |
| **MEDIUM** | 6 | Raw data storage, sync DB, session race condition, input validation, no HTTPS, header forwarding |
| **LOW** | 4 | Log verbosity, swallowed errors, timing attack, filename injection |

### Top 5 Attack Vectors
1. **Auth bypass** — Empty `COMMAND_CENTER_API_KEY` grants full API access
2. **API key extraction** — `NEXT_PUBLIC_API_KEY` visible in browser JS bundle
3. **Credit drain** — No rate limiting on Apollo/Anthropic-calling endpoints
4. **Prompt injection** — `custom_instructions` directly interpolated into LLM prompts
5. **Data injection** — Lead field values injected into LLM prompts without sanitization

---

## 7. Architecture Assessment

### What's Good
- Clean layered architecture: API routes → services → models/DB
- Proper Pydantic models for all API I/O
- Well-structured Apollo client with retry logic
- AI functions accept `BaseChatModel` as dependency injection — testable
- Type hints on all public functions
- Named exports (except Next.js pages)
- Uses `langchain_core` not `langchain` (per CLAUDE.md)

### What Breaks at Scale
1. **Sync SQLAlchemy** blocks the event loop — nonlinear performance degradation
2. **`asyncio.create_task`** for pipelines — work lost on server restart
3. **SQLite** — single-writer database, no concurrent writes
4. **Sequential LLM calls** — O(n) API requests per pipeline run
5. **No rate limiting** — single client can exhaust resources
6. **In-memory CSV export** — OOM risk on large datasets
7. **`raw_data` JSON blobs** — memory growth on lead listings

### Migration Path
| Phase | Focus | Effort | Items |
|-------|-------|--------|-------|
| 1 | Security & Data Integrity (P0) | ~4 hours | Auth, session bug, CSV injection, CORS, .gitignore |
| 2 | Architectural Fixes (P1) | ~3 days | Async SQLAlchemy, pipeline safety, concurrent LLM, rate limiting, indexes |
| 3 | Operational Health (P2) | ~2 days | Alembic migrations, health checks, error boundaries, logging |
| 4 | AI Reliability | ~1-2 days | Structured output, caching, prompt hardening, cost tracking |
| 5 | Frontend Polish | Ongoing | Error boundaries, SWR/TanStack Query, server components, skeletons, a11y |

---

## 8. Phased Implementation Plan

### Phase 1: P0 — Security & Data Integrity (Do Now)

| Fix | File(s) | Complexity | Description |
|-----|---------|-----------|-------------|
| 1.1 | `auth.py` | S | Fail closed when API key not configured |
| 1.2 | `auth.py` | S | Use `hmac.compare_digest` for key comparison |
| 1.3 | `frontend/src/lib/api.ts`, new proxy route | M | Remove `NEXT_PUBLIC_API_KEY`, proxy through server-side |
| 1.4 | `campaigns.py`, `pipeline.py` | M | Pipeline creates own DB session, not request's |
| 1.5 | `export_service.py` | S | Sanitize CSV cells against formula injection |
| 1.6 | `message_generator.py`, `outreach.py` | M | Sanitize `custom_instructions`, add prompt guardrails |
| 1.7 | `models/lead.py` | S | Add `cascade="all, delete-orphan"` to relationships |
| 1.8 | `main.py` | S | Restrict CORS methods/headers to specific values |

### Phase 2: P1 — Architectural Fixes (This Week)

| Fix | File(s) | Complexity | Description |
|-----|---------|-----------|-------------|
| 2.1 | `database.py`, ALL API/service files | L | Migrate to async SQLAlchemy |
| 2.2 | `pipeline.py`, `models/lead.py` | M | Add transaction safety + `pipeline_error` column |
| 2.3 | `lead_scorer.py`, `message_generator.py` | M | Parallelize LLM calls with `asyncio.gather` |
| 2.4 | `main.py` | M | Configure `slowapi` rate limiting |
| 2.5 | `models/lead.py` | S | Add missing indexes |
| 2.6 | `lead_scorer.py`, `message_generator.py` | S | Log LLM parse failures |

### Phase 3: P2 — Operational Health (Next Sprint)

| Fix | File(s) | Complexity | Description |
|-----|---------|-----------|-------------|
| 3.1 | New `alembic/` directory | M | Initialize Alembic, create initial migration |
| 3.2 | `main.py` | S | Deep health check (verify DB connectivity) |
| 3.3 | New `error.tsx`, `global-error.tsx` | S | Add React error boundaries |
| 3.4 | New `.gitignore` | S | Protect DB, cache, env files |
| 3.5 | `Caddyfile` | S | Fix `/leadgen*` → `/leadgen/*` routing |

---

## 9. Skeptical Review of the Plan

### Hidden Dependencies
- Fix 1.7 (cascades) is **blocked by** Fix 3.1 (migrations) for existing databases
- Fix 2.1 (async SQLAlchemy) should happen **after** Fix 1.4 (pipeline session)
- Fix 2.3 (concurrent LLM) should happen **after** Fix 2.1 (async DB)
- Fix 2.5 (indexes) is **blocked by** Fix 3.1 (migrations) for existing databases
- Fix 1.3 (BFF proxy) depends on Fix 1.1 (auth bypass) being deployed first

### Riskiest Change
**Fix 2.1 (Async SQLAlchemy)** — Cross-cutting refactor touching every data access path. Every `db.query()` becomes `await db.execute(select(...))`. A single missed `await` produces a runtime error. Requires comprehensive test coverage before attempting.

### What's Missing
1. **Secret rotation** — If API key was exposed via `NEXT_PUBLIC_`, rotate it immediately
2. **Apollo API key validation** — Empty key causes non-descriptive errors
3. **Test coverage assessment** — Must verify existing test depth before major refactors
4. **Frontend `default export` exception** — Document that Next.js pages are exempt from the named-export rule

### Minimum Viable Fix for Production Safety
If you can only do 6 things:
1. Fix auth bypass + timing attack (~30 min)
2. Fix pipeline session bug (~1 hour)
3. Fix CSV injection (~20 min)
4. Restrict CORS (~10 min)
5. Add .gitignore (~5 min)
6. Remove API key from client-side JS + rotate key (~2 hours)

**Total: ~4 hours for production safety.**

---

## 10. Questions for the Author

1. **Is the "Send" action intentionally fake?** The `outreach/send` endpoint (outreach.py:71-104) only marks messages as "sent" in the database but doesn't actually send anything. Is this scaffolding, or is there a missing integration?

2. **What is the plan for `asyncio.create_task` + sync session?** Is a task queue (Celery/ARQ) on the roadmap, or will fire-and-forget coroutines continue?

3. **Is `lead_gen.db` intentionally tracked in git?** There is no `.gitignore` entry for it.

4. **Is `langchain-anthropic` installed manually?** It's required at runtime (`utils/llm.py:25`) but missing from `requirements.txt`.

5. **What is the test plan for AI features?** Zero tests exist for pipeline, ICP parsing, lead scoring, outreach generation, CSV export, or the Apollo client — these are the core value-producing features.

---

*Report generated by 9 parallel AI agents analyzing backend, frontend, AI/LLM, deployment, security, and architecture.*
