# AI SDR OS — Skills Registry

Skills are reusable capabilities that power the AI SDR system. Each skill can be used independently or chained together.

---

## Lead Scoring

**Description**: Score leads 0-100 based on ICP fit using multi-criteria AI analysis.

**When to use**: After searching leads, before enrichment (saves credits by only enriching high-score leads).

**Implementation**: Claude Haiku with structured scoring prompt. Four criteria: Title/Seniority (0-30), Company Fit (0-30), Contact Quality (0-20), Engagement Signals (0-20). Returns JSON with score + reason.

**File**: `src/scoring/lead_scorer.py`

---

## Cold Email Personalization

**Description**: Generate personalized cold email outreach (subject + body) tailored to each lead's profile.

**When to use**: After enrichment, when leads have full profile data for personalization.

**Implementation**: Claude Haiku with lead context (title, company, industry, seniority). Generates under 150 words, one CTA, no spam triggers. Supports configurable tone (professional, casual, aggressive).

**File**: `src/outreach/message_generator.py`

---

## LinkedIn Message Generation

**Description**: Generate short LinkedIn connection/InMail messages (under 300 chars).

**When to use**: As an alternative or complement to email outreach.

**Implementation**: Same generator as email but with LinkedIn-specific constraints (shorter, more casual, no subject line).

**File**: `src/outreach/message_generator.py`

---

## ICP Interpretation

**Description**: Parse natural language ICP descriptions into structured Apollo.io search filters.

**When to use**: When user creates a new campaign with a text description.

**Implementation**: Claude Haiku extracts: person_titles, person_seniorities, person_locations, organization_industries, organization_locations, min/max_employees, keywords. Returns structured JSON.

**File**: `src/services/icp_parser.py`

---

## Apollo.io Lead Search

**Description**: Search Apollo's database of 275M+ contacts using structured filters.

**When to use**: First stage of campaign pipeline. Free (no credits consumed).

**Implementation**: POST to `/mixed_people/search` with filters. Returns basic lead info (name, title, company). Deduplicates against existing leads.

**File**: `src/services/apollo_client.py`

---

## Apollo.io Enrichment

**Description**: Enrich a lead with full contact data (email, phone, company details).

**When to use**: After scoring, for top-scoring leads only (costs 1 credit per lead).

**Implementation**: POST to `/people/match`. Supports bulk enrichment (10 per call). Updates lead record with email, phone, LinkedIn, company details.

**File**: `src/services/apollo_client.py`

---

## API Rate Limit Handling

**Description**: Handle API rate limits with exponential backoff and retry logic.

**When to use**: All external API calls (Apollo, Claude).

**Implementation**: tenacity library with `stop_after_attempt(3)`, `wait_exponential(multiplier=2, min=2, max=16)`. Detects 429 responses and retries automatically.

**File**: `src/services/apollo_client.py`

---

## Pipeline Orchestration

**Description**: Execute multi-stage campaign pipeline as a background task.

**When to use**: When user triggers "Run Pipeline" on a campaign.

**Implementation**: Sequential async stages (search → score → enrich → draft) with database-tracked stage transitions. Uses asyncio.create_task for non-blocking execution.

**File**: `src/services/pipeline.py`

---

## CSV Data Export

**Description**: Export lead data as downloadable CSV files.

**When to use**: When user wants to export campaign results.

**Implementation**: Python csv module with StreamingResponse. Configurable columns, score/status filters.

**File**: `src/services/export_service.py`

---

## CRM Data Modeling

**Description**: Track deal pipeline stages with automatic lead status updates.

**When to use**: When qualifying leads and tracking conversion.

**Implementation**: CRMDeal model with stages (prospect → discovery → proposal → negotiation → closed_won/closed_lost). Stage changes automatically update lead status.

**File**: `src/api/deals.py`, `src/models/lead.py`

---

## Lead Deduplication

**Description**: Prevent duplicate leads when searching Apollo multiple times.

**When to use**: During lead search and storage.

**Implementation**: Check `apollo_id` uniqueness before inserting. Skip existing leads, return them in results without re-inserting.

**File**: `src/services/lead_service.py`

---

## SaaS Dashboard UX Patterns

**Description**: Clean, minimal dashboard design patterns for B2B SaaS.

**When to use**: All frontend development.

**Implementation**: Linear-inspired design system. White cards, subtle borders, Inter font, blue accent. Sortable tables, tag-based filters, pipeline progress indicators, side panels for detail views.

**File**: `frontend/src/app/globals.css`, component library

---

## Proposed Future Skills

| Skill | Description | Priority |
|-------|-------------|----------|
| A/B Subject Lines | Generate multiple subject variants for testing | Medium |
| Follow-Up Generator | Create follow-up emails based on no-reply | Medium |
| Company Research | Aggregate news/funding/hiring signals | Low |
| Lead Re-Scoring | Re-evaluate scores after enrichment adds data | Medium |
| Suppression List | Maintain global do-not-contact list | High |
| ICP Refinement | Suggest ICP improvements based on conversion data | Low |
| Domain Reputation | Check sender domain health before email | Medium |
