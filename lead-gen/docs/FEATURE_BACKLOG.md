# AI SDR OS — Feature Backlog

## CRM Integrations
- HubSpot: Push qualified leads as contacts, create deals
- Salesforce: Contact/Opportunity sync
- Pipedrive: Deal pipeline integration
- Webhook-based: Generic CRM push via configurable webhooks

## Outreach Automation
- Email sending via SendGrid / AWS SES / Mailgun
- LinkedIn connection requests via automation
- Apollo sequences integration (add contacts to existing sequences)
- Multi-step drip campaigns (follow-up emails on day 3, 7, 14)
- Send scheduling (optimal send times by timezone)

## Analytics & Reporting
- Campaign performance dashboard (open rates, reply rates, conversion)
- Lead source attribution (which ICP descriptions produce best leads)
- Score calibration (compare AI scores to actual outcomes)
- Cost tracking (Apollo credits used, Claude tokens consumed)
- ROI calculator (deals closed vs. credits spent)

## AI Improvements
- A/B test subject line generation (multiple variants per lead)
- Follow-up email generation based on no-reply
- Lead re-scoring after enrichment (more data = better score)
- ICP refinement suggestions based on successful conversions
- Tone/style learning from user edits
- Company research integration (news, funding, hiring signals)

## Campaign Optimization
- Smart lead deduplication across campaigns
- Suppression lists (global + per-campaign)
- Domain blacklists (competitors, existing customers)
- Automatic re-search on campaigns with low lead count
- Lookalike lead discovery (find similar to best-scored leads)

## User Experience
- Dark mode
- Keyboard shortcuts (j/k navigation, enter to open, esc to close)
- Drag-and-drop pipeline board view
- Real-time pipeline progress (WebSocket)
- Saved ICP templates (reuse common search criteria)
- Campaign cloning
- Undo/redo for draft edits
- In-app notifications for pipeline completion

## Data & Import
- CSV import (bring your own lead list)
- LinkedIn Sales Navigator import
- Google Sheets integration
- Lead merge (combine duplicates)
- Data quality scores (completeness, freshness)

## Security & Compliance
- Multi-tenant user auth (JWT + email/password)
- Role-based access control (admin, user, viewer)
- GDPR compliance (data deletion, consent tracking)
- Audit log (who did what, when)
- API rate limiting per user/tenant
- SOC 2 readiness checklist

## Infrastructure
- PostgreSQL with connection pooling
- Redis for caching + job queues
- Background worker for pipeline execution
- Webhook endpoint for Apollo delivery tracking
- Health monitoring + alerting
- Database backup automation
- Horizontal scaling (multiple workers)
