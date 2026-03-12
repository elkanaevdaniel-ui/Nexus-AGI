# AI SDR OS — Database Schema

## Overview

SQLite for development, PostgreSQL for production. SQLAlchemy 2.0 ORM with Pydantic models for serialization.

## Tables

### campaigns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | STRING | PK | uuid4 | |
| name | STRING | NOT NULL | | Campaign name |
| description | TEXT | YES | | |
| icp_raw_text | TEXT | YES | | Original natural language ICP input |
| parsed_filters | TEXT | YES | | JSON of parsed Apollo filters |
| target_titles | TEXT | YES | | Comma-separated job titles |
| target_industries | TEXT | YES | | Comma-separated industries |
| target_seniority | TEXT | YES | | Comma-separated seniority levels |
| target_locations | TEXT | YES | | Comma-separated locations |
| min_employees | INTEGER | YES | | Min company size |
| max_employees | INTEGER | YES | | Max company size |
| keywords | TEXT | YES | | Search keywords |
| status | STRING | NO | "active" | active / paused / completed |
| pipeline_stage | STRING | NO | "idle" | idle / searching / scoring / enriching / drafting / complete / failed |
| total_leads | INTEGER | NO | 0 | |
| enriched_leads | INTEGER | NO | 0 | |
| contacted_leads | INTEGER | NO | 0 | |
| created_at | DATETIME | NO | utcnow | |
| updated_at | DATETIME | NO | utcnow | Auto-updated |

**Indexes**: `id` (PK)

### leads

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | STRING | PK | uuid4 | |
| apollo_id | STRING | YES | | Unique, indexed |
| first_name | STRING | NOT NULL | | |
| last_name | STRING | NOT NULL | | |
| email | STRING | YES | | Indexed |
| email_status | STRING | YES | | verified / guessed / unavailable |
| phone | STRING | YES | | |
| linkedin_url | STRING | YES | | |
| title | STRING | YES | | Job title |
| seniority | STRING | YES | | |
| department | STRING | YES | | |
| headline | STRING | YES | | |
| company_name | STRING | YES | | Indexed |
| company_domain | STRING | YES | | |
| company_industry | STRING | YES | | |
| company_size | INTEGER | YES | | Employee count |
| company_revenue | STRING | YES | | |
| company_location | STRING | YES | | |
| source | STRING | NO | "apollo" | apollo / manual / import |
| status | STRING | NO | "new" | new / enriched / scored / contacted / qualified / converted / lost |
| score | INTEGER | NO | 0 | AI score 0-100 |
| score_reason | TEXT | YES | | AI explanation |
| campaign_id | STRING | FK | | → campaigns.id |
| raw_data | TEXT | YES | | JSON dump from Apollo |
| created_at | DATETIME | NO | utcnow | |
| updated_at | DATETIME | NO | utcnow | Auto-updated |

**Indexes**: `id` (PK), `apollo_id` (unique), `email`, `company_name`, `status`
**FK**: `campaign_id` → `campaigns.id`

### outreach_messages

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | STRING | PK | uuid4 | |
| lead_id | STRING | FK, NOT NULL | | → leads.id |
| campaign_id | STRING | FK | | → campaigns.id |
| channel | STRING | NOT NULL | | email / linkedin / apollo_sequence |
| sequence_step | INTEGER | NO | 1 | |
| subject | STRING | YES | | Email subject line |
| body | TEXT | NOT NULL | | Message body |
| status | STRING | NO | "draft" | draft / sent / delivered / opened / replied / bounced |
| apollo_sequence_id | STRING | YES | | |
| sent_at | DATETIME | YES | | |
| opened_at | DATETIME | YES | | |
| replied_at | DATETIME | YES | | |
| created_at | DATETIME | NO | utcnow | |

**FK**: `lead_id` → `leads.id`, `campaign_id` → `campaigns.id`

### crm_deals

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | STRING | PK | uuid4 | |
| lead_id | STRING | FK, UNIQUE, NOT NULL | | → leads.id |
| title | STRING | NOT NULL | | |
| value | FLOAT | NO | 0.0 | Deal value |
| currency | STRING | NO | "USD" | |
| stage | STRING | NO | "prospect" | prospect / discovery / proposal / negotiation / closed_won / closed_lost |
| probability | INTEGER | NO | 10 | 0-100 |
| notes | TEXT | YES | | |
| next_action | STRING | YES | | |
| next_action_date | DATETIME | YES | | |
| created_at | DATETIME | NO | utcnow | |
| updated_at | DATETIME | NO | utcnow | Auto-updated |

**FK**: `lead_id` → `leads.id` (unique — one deal per lead)

## Relationships

```
Campaign 1──────N Lead 1──────1 CRMDeal
                  │
                  1
                  │
                  N
            OutreachMessage
```

## New Fields (V1 Additions)

Added to `campaigns` table:
- `icp_raw_text` — stores the original plain-English ICP
- `parsed_filters` — JSON string of structured Apollo search parameters
- `pipeline_stage` — tracks current automation stage

## Migration Strategy

For V1 (SQLite dev): Drop and recreate via `init_db()`.
For production (PostgreSQL): Use Alembic migrations.
