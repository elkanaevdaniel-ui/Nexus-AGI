# AI SDR OS — API Design

Base URL: `http://localhost:8082`
Auth: `x-api-key` header

## Campaigns

### POST /api/campaigns
Create a campaign.

**Request:**
```json
{
  "name": "Cybersecurity MSSPs Israel",
  "description": "Find cybersecurity MSSPs and resellers in Israel",
  "target_titles": "CEO,CTO,Founder",
  "target_industries": "cybersecurity",
  "target_seniority": "c_suite,founder,vp",
  "target_locations": "Israel",
  "min_employees": 10,
  "max_employees": 200,
  "keywords": "MSSP,reseller,managed security"
}
```

**Response:** `CampaignResponse` (200)

### POST /api/campaigns/parse-icp *(NEW)*
Parse natural language ICP into structured filters.

**Request:**
```json
{
  "icp_text": "Find cybersecurity MSSPs and resellers in Israel with 10-200 employees. Prefer founders, CEOs, channel managers, and sales directors."
}
```

**Response:**
```json
{
  "person_titles": ["Founder", "CEO", "Channel Manager", "Sales Director"],
  "person_seniorities": ["founder", "c_suite", "director"],
  "person_locations": ["Israel"],
  "organization_industries": ["cybersecurity", "information technology & services"],
  "organization_locations": ["Israel"],
  "min_employees": 10,
  "max_employees": 200,
  "keywords": ["MSSP", "reseller", "managed security"]
}
```

### POST /api/campaigns/run-pipeline *(NEW)*
Trigger the full automation pipeline for a campaign.

**Request:**
```json
{
  "campaign_id": "uuid",
  "enrich_top_n": 20,
  "min_score_for_enrichment": 60
}
```

**Response:**
```json
{
  "status": "started",
  "campaign_id": "uuid",
  "pipeline_stage": "searching"
}
```

### GET /api/campaigns/{id}/pipeline-status *(NEW)*
Get current pipeline progress.

**Response:**
```json
{
  "campaign_id": "uuid",
  "pipeline_stage": "scoring",
  "total_leads": 142,
  "scored_leads": 89,
  "enriched_leads": 0,
  "drafts_generated": 0,
  "started_at": "2026-03-07T10:00:00Z"
}
```

### GET /api/campaigns
List all campaigns. Returns `CampaignResponse[]`.

### GET /api/campaigns/{id}
Get single campaign.

### PATCH /api/campaigns/{id}
Update campaign fields.

### DELETE /api/campaigns/{id}
Delete campaign (204).

---

## Leads

### POST /api/leads/search
Search Apollo.io and store results.

**Request:** `ApolloSearchRequest`
```json
{
  "person_titles": ["CEO", "CTO"],
  "person_seniorities": ["c_suite"],
  "person_locations": ["Israel"],
  "organization_num_employees_ranges": ["10,200"],
  "campaign_id": "uuid",
  "page": 1,
  "per_page": 25
}
```

**Response:** `SearchResponse` with leads array + pagination.

### POST /api/leads/enrich
Enrich leads via Apollo (costs credits).

**Request:** `{ "lead_ids": ["id1", "id2"] }` (max 10)
**Response:** `EnrichResponse` with enriched/failed counts.

### POST /api/leads/score
Score leads using AI.

**Request:** `{ "campaign_id": "uuid" }` or `{ "lead_ids": [...] }`
**Response:** `ScoreResponse` with scored count + leads.

### GET /api/leads
List leads with filters.

**Query params:** `campaign_id`, `status`, `min_score`, `limit`, `offset`

### GET /api/leads/stats
Pipeline statistics.

### GET /api/leads/{id}
Get single lead.

### PATCH /api/leads/{id}
Update lead status/score.

### DELETE /api/leads/{id}
Delete lead (204).

---

## Outreach

### POST /api/outreach/generate
Generate AI outreach messages.

**Request:**
```json
{
  "lead_ids": ["id1", "id2"],
  "channel": "email",
  "tone": "professional",
  "custom_instructions": "Mention our ISO 27001 certification"
}
```

### POST /api/outreach/send
Mark messages as sent (stub — no actual sending in V1).

### GET /api/outreach
List messages. Filter by `lead_id`, `status`.

### GET /api/outreach/{id}
Get single message.

### DELETE /api/outreach/{id}
Delete message (204).

---

## Deals

### POST /api/deals
Create deal for a lead.

### GET /api/deals
List deals. Filter by `stage`.

### GET /api/deals/{id}
Get single deal.

### PATCH /api/deals/{id}
Update deal stage/value.

---

## Export *(NEW)*

### GET /api/campaigns/{id}/export
Export campaign leads as CSV.

**Query params:** `format=csv`, `min_score=0`, `status=all`

**Response:** `Content-Type: text/csv` streaming download.

**CSV Columns:**
```
Name,Email,Email Status,Phone,Title,Seniority,Company,Industry,Size,Location,Score,Score Reason,Status
```

---

## Apollo.io Integration

| Endpoint | Apollo API | Credits | Notes |
|----------|-----------|---------|-------|
| Lead search | POST /mixed_people/search | Free | Returns IDs + basic info |
| Enrich person | POST /people/match | 1/lead | Full contact data |
| Bulk enrich | POST /people/bulk_match | 1/lead | Up to 10 per call |
| Org search | POST /mixed_companies/search | Free | Company data |

## Claude Integration

| Feature | Model | Input | Output |
|---------|-------|-------|--------|
| ICP Parser | Haiku | Natural language text | JSON filters |
| Lead Scorer | Haiku | Lead profile + ICP | Score (0-100) + reason |
| Outreach Gen | Haiku | Lead profile + tone | Subject + body |

---

## Error Responses

All errors return:
```json
{
  "detail": "Error description"
}
```

| Status | Meaning |
|--------|---------|
| 400 | Invalid request body |
| 401 | Missing/invalid API key |
| 404 | Resource not found |
| 409 | Conflict (duplicate) |
| 422 | Validation error |
| 429 | Rate limited |
| 500 | Internal server error |
