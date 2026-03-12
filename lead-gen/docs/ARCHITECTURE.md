# AI SDR OS — Architecture

## System Overview

```
┌──────────────────────────────────────────────────────────┐
│                    Next.js Frontend                       │
│              (localhost:3000)                             │
│  Dashboard │ Campaigns │ Prospects │ Drafts │ Export     │
└──────────────────────┬───────────────────────────────────┘
                       │ HTTP/JSON
┌──────────────────────┴───────────────────────────────────┐
│                   FastAPI Backend                         │
│              (localhost:8082)                             │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │ Campaign │  │   Lead   │  │ Outreach │  │  Deal   │ │
│  │   API    │  │   API    │  │   API    │  │  API    │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬────┘ │
│       │              │              │              │      │
│  ┌────┴──────────────┴──────────────┴──────────────┴───┐ │
│  │                 Service Layer                        │ │
│  │  ICP Parser │ Lead Service │ Scorer │ Pipeline      │ │
│  └──────┬───────────┬────────────┬─────────────────────┘ │
│         │           │            │                        │
│  ┌──────┴───┐ ┌─────┴────┐ ┌────┴─────┐                │
│  │ Claude   │ │ Apollo   │ │ SQLite   │                │
│  │ (LLM)   │ │ (API)    │ │ (DB)     │                │
│  └──────────┘ └──────────┘ └──────────┘                │
└──────────────────────────────────────────────────────────┘
```

## Data Flow — Campaign Pipeline

```
User Input (natural language ICP)
    │
    ▼
[1. ICP Parser] ──── Claude AI ────→ Structured Filters
    │
    ▼
[2. Lead Search] ── Apollo.io ────→ Raw Leads (free, no credits)
    │
    ▼
[3. Lead Scoring] ── Claude AI ───→ Scored Leads (0-100)
    │
    ▼
[4. Enrichment] ─── Apollo.io ───→ Full Contact Data (costs credits)
    │                                (only top-scored leads)
    ▼
[5. Draft Gen] ──── Claude AI ───→ Email + LinkedIn Drafts
    │
    ▼
[6. Human Review] ─────────────→ Approve / Edit / Reject
    │
    ▼
[7. Export] ─────────────────────→ CSV Download
```

## Backend Services

### API Layer (`src/api/`)

| Router | Prefix | Endpoints |
|--------|--------|-----------|
| campaigns | `/api/campaigns` | CRUD + parse-icp + run-pipeline + pipeline-status |
| leads | `/api/leads` | CRUD + search + enrich + score + stats |
| outreach | `/api/outreach` | generate + send + CRUD |
| deals | `/api/deals` | CRUD |

### Service Layer (`src/services/`)

| Service | File | Responsibility |
|---------|------|---------------|
| ApolloClient | `apollo_client.py` | HTTP client for Apollo.io API with retry logic |
| LeadService | `lead_service.py` | Search, store, enrich, deduplicate leads |
| ICPParser | `icp_parser.py` | Claude-powered NLP → structured Apollo filters |
| Pipeline | `pipeline.py` | Orchestrate full campaign pipeline (async background task) |
| ExportService | `export_service.py` | Generate CSV exports |

### AI Layer

| Component | File | Model | Purpose |
|-----------|------|-------|---------|
| Lead Scorer | `scoring/lead_scorer.py` | Claude Haiku | Score leads 0-100 against ICP |
| Message Generator | `outreach/message_generator.py` | Claude Haiku | Personalized email/LinkedIn drafts |
| ICP Parser | `services/icp_parser.py` | Claude Haiku | Parse natural language → filters |

### Data Layer

| Component | File | Technology |
|-----------|------|-----------|
| ORM Models | `models/lead.py` | SQLAlchemy 2.0 |
| Database | `database.py` | SQLite (dev) / PostgreSQL (prod) |
| Schemas | `schemas.py` | Pydantic v2 |

## Pipeline Orchestration

The pipeline runs as a background `asyncio` task (no Redis/worker needed for V1):

```python
async def run_campaign_pipeline(campaign_id, db):
    # Stage 1: Search Apollo (free)
    update_stage("searching")
    leads = await search_apollo(campaign)

    # Stage 2: Score with AI
    update_stage("scoring")
    scored = await score_leads(leads)

    # Stage 3: Enrich top leads (costs credits)
    update_stage("enriching")
    top_leads = filter(score >= threshold)
    await enrich_leads(top_leads)

    # Stage 4: Generate outreach drafts
    update_stage("drafting")
    await generate_drafts(enriched_leads)

    # Stage 5: Ready for review
    update_stage("complete")
```

## Authentication

- API key in `x-api-key` header
- Configured via `COMMAND_CENTER_API_KEY` env var
- If no key configured: all requests allowed (dev mode)

## Configuration

All config via root `.env` file (no service-specific .env files):

```
APOLLO_API_KEY=<key>
ANTHROPIC_API_KEY=<key>
LEAD_GEN_PORT=8082
LEAD_GEN_DB_URL=sqlite:///./lead_gen.db
COMMAND_CENTER_API_KEY=<key>
CORS_ORIGINS=http://localhost:3000,http://localhost:3001
```

## Error Handling

- Apollo API: tenacity retry with exponential backoff (3 attempts, 2-16s)
- Claude API: JSON parsing fallback on malformed responses
- Pipeline: Stage set to "failed" on unrecoverable errors
- All endpoints return proper HTTP status codes + Pydantic error models

## Deployment (V1)

Single server, two processes:
1. `uvicorn` for FastAPI backend (port 8082)
2. `next dev` / `next start` for frontend (port 3000)

No Docker, no Redis, no workers needed for solo founder scale.
