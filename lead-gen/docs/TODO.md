# AI SDR OS — Engineering TODO

## Backend

### High Priority
- [ ] Create ICP parser service (`src/services/icp_parser.py`)
- [ ] Create pipeline orchestrator (`src/services/pipeline.py`)
- [ ] Create export service (`src/services/export_service.py`)
- [ ] Add `icp_raw_text`, `parsed_filters`, `pipeline_stage` to Campaign model
- [ ] Add ICP/pipeline Pydantic schemas
- [ ] Add `POST /api/campaigns/parse-icp` endpoint
- [ ] Add `POST /api/campaigns/run-pipeline` endpoint
- [ ] Add `GET /api/campaigns/{id}/pipeline-status` endpoint
- [ ] Add `GET /api/campaigns/{id}/export` endpoint

### Medium Priority
- [ ] Add `PATCH /api/outreach/{id}` for editing drafts
- [ ] Add bulk lead status update endpoint
- [ ] Add campaign lead count to list response

### Low Priority
- [ ] Rate limit tracking (Apollo credits remaining)
- [ ] Outreach daily limit enforcement
- [ ] Structured logging (JSON format)

## Frontend

### High Priority
- [ ] Initialize Next.js 15+ app with TypeScript strict + Tailwind
- [ ] Create layout with Sidebar component
- [ ] Campaign Dashboard page (`/`)
- [ ] New Campaign page (`/campaigns/new`) with ICP textarea + filter preview
- [ ] Campaign Detail page (`/campaigns/[id]`) with pipeline progress
- [ ] Prospect Table page (`/campaigns/[id]/prospects`) with sorting/filtering
- [ ] Draft Review page (`/campaigns/[id]/drafts`) with editable fields
- [ ] Export page (`/campaigns/[id]/export`)

### Medium Priority
- [ ] Prospect Detail side panel
- [ ] Score breakdown visualization
- [ ] Bulk action UI (select all, approve all)
- [ ] Pipeline status polling with auto-refresh

### Low Priority
- [ ] Mobile-responsive table
- [ ] Keyboard shortcuts
- [ ] Dark mode toggle

## Integrations

### Implemented
- [x] Apollo.io search API
- [x] Apollo.io enrichment API
- [x] Claude scoring API
- [x] Claude outreach generation API

### Needed
- [ ] ICP parsing via Claude (new)
- [ ] CSV export generation

### Future
- [ ] Email sending (SendGrid/SES)
- [ ] LinkedIn automation
- [ ] Apollo sequences API
- [ ] CRM webhook (HubSpot/Salesforce)

## AI Systems

### Implemented
- [x] Lead scoring prompt + JSON parsing
- [x] Outreach message generation (email + LinkedIn)

### Needed
- [ ] ICP interpretation prompt
- [ ] Structured output validation for ICP parser

### Future
- [ ] A/B test subject line generation
- [ ] Follow-up email generation
- [ ] Lead re-scoring after enrichment

## Infrastructure

### In Place
- [x] SQLite database with SQLAlchemy ORM
- [x] API key authentication
- [x] CORS configuration
- [x] Start script

### Needed
- [ ] Frontend start script
- [ ] Combined start script (backend + frontend)

### Future
- [ ] PostgreSQL migration
- [ ] Docker Compose setup
- [ ] Systemd service files
- [ ] Caddy reverse proxy config
- [ ] GitHub Actions CI/CD
