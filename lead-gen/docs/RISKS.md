# AI SDR OS — Risks

## Technical Risks

### Apollo.io API Reliability
- **Risk**: API rate limits (50/min free, 200/min paid), downtime, response format changes
- **Impact**: High — core data source, no fallback
- **Mitigation**: Retry logic with exponential backoff (already implemented), cache search results, monitor rate limit headers

### Apollo.io Credit Consumption
- **Risk**: Enrichment costs 1 credit per lead. Uncontrolled enrichment burns credits fast.
- **Impact**: High — direct cost
- **Mitigation**: Only enrich leads above score threshold, batch enrichment (10 at a time), display credits remaining in UI

### Claude API Costs
- **Risk**: Scoring + outreach generation costs add up with many leads
- **Impact**: Medium — Claude Haiku is cheap (~$0.25/1M tokens) but scales linearly
- **Mitigation**: Use Haiku (cheapest model), batch scoring prompts, cache results, set campaign lead limits

### LLM Output Quality
- **Risk**: Claude may generate poor scores, miss JSON format, or produce generic outreach
- **Impact**: Medium — bad scores lead to wrong leads enriched (wasted credits)
- **Mitigation**: JSON parsing fallback (already implemented), score validation (0-100 clamping), human review required before any action

### SQLite Limitations
- **Risk**: No concurrent writes, no network access, limited to single server
- **Impact**: Low for V1 (solo founder), High if scaling
- **Mitigation**: PostgreSQL migration path documented, SQLAlchemy ORM makes switch trivial

### Pipeline Background Tasks
- **Risk**: asyncio.create_task may lose jobs on server restart
- **Impact**: Medium — pipeline stops mid-execution
- **Mitigation**: Pipeline stage tracking in DB, restart capability, idempotent operations. Upgrade to Redis/arq when needed.

## Business Risks

### Apollo.io Pricing Changes
- **Risk**: Apollo may change API pricing, restrict features, or require higher-tier plans
- **Impact**: High — product depends on Apollo
- **Mitigation**: Abstract data source behind interface. Could add alternative providers (Hunter.io, Clearbit, RocketReach)

### Email Deliverability
- **Risk**: AI-generated cold emails may trigger spam filters
- **Impact**: High — defeats the purpose
- **Mitigation**: Human review required, personalization focus, comply with CAN-SPAM, warm-up sending domain

### Data Privacy / GDPR
- **Risk**: Storing personal contact data has legal implications in EU
- **Impact**: Medium — potential legal liability
- **Mitigation**: V1 targets non-EU markets. Add GDPR compliance (consent tracking, data deletion) before EU expansion.

### Competition
- **Risk**: Established players (Instantly, Apollo itself, Smartlead) offer similar features
- **Impact**: Medium — need clear differentiation
- **Mitigation**: Focus on simplicity + AI-native experience. Competitors are bloated; we're fast and focused.

## Scaling Risks

### Database Performance
- **Risk**: SQLite slows with >10K leads or concurrent users
- **Impact**: Low for V1
- **Mitigation**: Switch to PostgreSQL + add indexes. Schema is already indexed on key columns.

### API Response Times
- **Risk**: Claude + Apollo calls are slow (2-10s each). Pipeline with 100+ leads takes minutes.
- **Impact**: Medium — user waits
- **Mitigation**: Background pipeline with status polling. User doesn't wait for completion.

### Single Server
- **Risk**: One server, one process. No redundancy.
- **Impact**: Low for V1 (solo founder)
- **Mitigation**: Docker + systemd auto-restart. Scale to multiple workers when needed.

## Operational Risks

### Secret Management
- **Risk**: API keys in .env file, no rotation policy
- **Impact**: Medium — compromised keys = unauthorized access
- **Mitigation**: .env in .gitignore (already). Consider vault/SSM for production.

### No Monitoring
- **Risk**: No alerting on errors, rate limits, or failed pipelines
- **Impact**: Medium — silent failures
- **Mitigation**: Add structured logging (Phase 5). Integrate Sentry for error tracking.

### Data Loss
- **Risk**: SQLite file corruption or accidental deletion
- **Impact**: High — all lead data lost
- **Mitigation**: Regular backups. Use PostgreSQL for production.
