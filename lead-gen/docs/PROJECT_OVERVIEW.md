# AI SDR OS — Project Overview

## Purpose

AI SDR OS is an AI-powered Sales Development Representative operating system that transforms plain-English Ideal Customer Profile (ICP) descriptions into qualified leads, enriched contact data, and AI-generated outreach drafts.

The system automates the SDR research pipeline while keeping humans in the loop for approval and quality control.

## How It Works

1. User creates a campaign with a natural language ICP description
2. Claude AI parses the ICP into structured search filters
3. Apollo.io searches for matching leads
4. AI scoring engine ranks leads by fit (0-100)
5. Top leads are enriched with full contact data
6. Claude generates personalized outreach drafts (email + LinkedIn)
7. User reviews, edits, and approves outreach
8. Approved leads are exported as CSV

## Major Components

### Backend (FastAPI + Python)

| Service | Purpose | Location |
|---------|---------|----------|
| Campaign Manager | Create/manage ICP campaigns | `src/api/campaigns.py` |
| Lead Search | Apollo.io people search + storage | `src/services/lead_service.py` |
| Lead Scoring | Claude AI scoring (0-100) | `src/scoring/lead_scorer.py` |
| Enrichment | Apollo.io contact enrichment | `src/services/apollo_client.py` |
| Outreach Generator | Claude AI message drafts | `src/outreach/message_generator.py` |
| ICP Parser | NLP ICP → structured filters | `src/services/icp_parser.py` |
| Pipeline Orchestrator | Automated campaign pipeline | `src/services/pipeline.py` |
| Export Service | CSV export | `src/services/export_service.py` |
| CRM Deals | Simple deal tracking | `src/api/deals.py` |

### Frontend (Next.js + React)

| Page | Purpose |
|------|---------|
| Campaign Dashboard | List all campaigns with status |
| New Campaign | ICP input + filter preview |
| Campaign Detail | Pipeline progress + stats |
| Prospect Table | Sortable/filterable lead list |
| Draft Review | Edit/approve outreach messages |
| Export | Download campaign data as CSV |

### External Integrations

| Service | Purpose | Auth |
|---------|---------|------|
| Apollo.io | Lead search + enrichment | API key (`APOLLO_API_KEY`) |
| Claude (Anthropic) | ICP parsing, scoring, outreach | API key (`ANTHROPIC_API_KEY`) |

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy 2.0, Pydantic
- **Frontend**: Next.js 15+, React 19, TypeScript (strict), Tailwind CSS
- **Database**: SQLite (dev), PostgreSQL (prod)
- **AI**: Claude via langchain_core
- **HTTP**: httpx (async)
- **Retry**: tenacity (exponential backoff)

## Target User

Solo founders and small teams running outbound sales who want to automate lead research without expensive SDR tools.

## V1 Scope

- Single-user, API key auth
- SQLite database
- Manual pipeline trigger (no auto-scheduling)
- Human approval required before any outreach
- CSV export (no CRM integrations)
