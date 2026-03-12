"""Pydantic request/response models for Lead Gen API."""

from datetime import datetime

from pydantic import BaseModel, Field


# ── Campaign ──────────────────────────────────────────────

class CampaignCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    icp_raw_text: str | None = None
    parsed_filters: str | None = None
    target_titles: str | None = None
    target_industries: str | None = None
    target_seniority: str | None = None
    target_locations: str | None = None
    min_employees: int | None = None
    max_employees: int | None = None
    keywords: str | None = None


class CampaignResponse(BaseModel):
    id: str
    name: str
    description: str | None
    icp_raw_text: str | None
    parsed_filters: str | None
    target_titles: str | None
    target_industries: str | None
    target_seniority: str | None
    target_locations: str | None
    min_employees: int | None
    max_employees: int | None
    keywords: str | None
    status: str
    pipeline_stage: str
    total_leads: int
    enriched_leads: int
    contacted_leads: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CampaignUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None
    target_titles: str | None = None
    target_industries: str | None = None
    target_seniority: str | None = None
    target_locations: str | None = None
    min_employees: int | None = None
    max_employees: int | None = None
    keywords: str | None = None


# ── Lead ──────────────────────────────────────────────────

class LeadResponse(BaseModel):
    id: str
    first_name: str
    last_name: str
    email: str | None
    email_status: str | None
    phone: str | None
    linkedin_url: str | None
    title: str | None
    seniority: str | None
    department: str | None
    company_name: str | None
    company_domain: str | None
    company_industry: str | None
    company_size: int | None
    company_location: str | None
    source: str
    status: str
    score: int
    score_reason: str | None
    campaign_id: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LeadUpdate(BaseModel):
    status: str | None = None
    score: int | None = None
    notes: str | None = None


class BulkLeadStatusUpdate(BaseModel):
    lead_ids: list[str] = Field(..., min_length=1, max_length=200)
    status: str = Field(..., min_length=1)


# ── Search ────────────────────────────────────────────────

class ApolloSearchRequest(BaseModel):
    """Parameters for searching leads via Apollo.io."""
    person_titles: list[str] | None = None
    person_seniorities: list[str] | None = None
    q_organization_domains: list[str] | None = None
    organization_industry_tag_ids: list[str] | None = None
    organization_num_employees_ranges: list[str] | None = None
    person_locations: list[str] | None = None
    q_keywords: str | None = None
    page: int = 1
    per_page: int = 25
    campaign_id: str | None = None


class SearchResponse(BaseModel):
    leads: list[LeadResponse]
    total_found: int
    page: int
    per_page: int
    campaign_id: str | None


# ── Enrichment ────────────────────────────────────────────

class EnrichRequest(BaseModel):
    lead_ids: list[str] = Field(..., min_length=1, max_length=10)


class EnrichResponse(BaseModel):
    enriched: int
    failed: int
    leads: list[LeadResponse]


# ── Scoring ───────────────────────────────────────────────

class ScoreRequest(BaseModel):
    lead_ids: list[str] | None = None
    campaign_id: str | None = None


class ScoreResponse(BaseModel):
    scored: int
    leads: list[LeadResponse]


# ── Outreach ──────────────────────────────────────────────

class OutreachGenerateRequest(BaseModel):
    lead_ids: list[str] = Field(..., min_length=1, max_length=20)
    channel: str = "email"  # email / linkedin
    tone: str = "professional"
    custom_instructions: str | None = None


class OutreachMessageResponse(BaseModel):
    id: str
    lead_id: str
    channel: str
    sequence_step: int
    subject: str | None
    body: str
    status: str
    sent_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class OutreachGenerateResponse(BaseModel):
    messages: list[OutreachMessageResponse]


class OutreachUpdateRequest(BaseModel):
    subject: str | None = None
    body: str | None = None


class OutreachSendRequest(BaseModel):
    message_ids: list[str] = Field(..., min_length=1)


class OutreachSendResponse(BaseModel):
    sent: int
    failed: int


# ── CRM Deal ─────────────────────────────────────────────

class DealCreate(BaseModel):
    lead_id: str
    title: str
    value: float = 0.0
    currency: str = "USD"
    stage: str = "prospect"
    notes: str | None = None


class DealResponse(BaseModel):
    id: str
    lead_id: str
    title: str
    value: float
    currency: str
    stage: str
    probability: int
    notes: str | None
    next_action: str | None
    next_action_date: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DealUpdate(BaseModel):
    stage: str | None = None
    value: float | None = None
    probability: int | None = None
    notes: str | None = None
    next_action: str | None = None
    next_action_date: datetime | None = None


# ── ICP Parsing ──────────────────────────────────────────

class ICPParseRequest(BaseModel):
    icp_text: str = Field(..., min_length=10, max_length=2000)


class ICPParseResponse(BaseModel):
    person_titles: list[str] = []
    person_seniorities: list[str] = []
    person_locations: list[str] = []
    organization_industries: list[str] = []
    organization_locations: list[str] = []
    min_employees: int | None = None
    max_employees: int | None = None
    keywords: list[str] = []


# ── Pipeline ─────────────────────────────────────────────

class PipelineRunRequest(BaseModel):
    campaign_id: str
    enrich_top_n: int = Field(20, ge=1, le=100)
    min_score_for_enrichment: int = Field(60, ge=0, le=100)


class PipelineRunResponse(BaseModel):
    status: str
    campaign_id: str
    pipeline_stage: str


class PipelineStatusResponse(BaseModel):
    campaign_id: str
    pipeline_stage: str
    total_leads: int
    scored_leads: int
    enriched_leads: int
    drafts_generated: int


# ── Campaign from ICP ────────────────────────────────────

class CampaignCreateFromICP(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    icp_text: str = Field(..., min_length=10, max_length=2000)
    auto_run: bool = False
    enrich_top_n: int = Field(20, ge=1, le=100)
    min_score_for_enrichment: int = Field(60, ge=0, le=100)


# ── Dashboard / Stats ────────────────────────────────────

class LeadImport(BaseModel):
    """Single lead for bulk import."""
    first_name: str
    last_name: str
    email: str | None = None
    email_status: str | None = None
    phone: str | None = None
    linkedin_url: str | None = None
    title: str | None = None
    seniority: str | None = None
    department: str | None = None
    headline: str | None = None
    company_name: str | None = None
    company_domain: str | None = None
    company_industry: str | None = None
    company_size: int | None = None
    company_revenue: str | None = None
    company_location: str | None = None


class BulkImportRequest(BaseModel):
    """Bulk import leads into a campaign."""
    campaign_id: str
    leads: list[LeadImport] = Field(..., min_length=1, max_length=500)


class BulkImportResponse(BaseModel):
    imported: int
    campaign_id: str
    lead_ids: list[str]


class PipelineStats(BaseModel):
    total_leads: int
    new: int
    enriched: int
    scored: int
    contacted: int
    qualified: int
    converted: int
    lost: int
    total_deals_value: float
    avg_score: float
