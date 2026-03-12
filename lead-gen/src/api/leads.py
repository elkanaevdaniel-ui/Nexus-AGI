"""Lead management and Apollo.io integration API routes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.auth import verify_api_key
from src.database import get_db
from src.models.lead import Lead, OutreachMessage
from src.schemas import (
    ApolloSearchRequest,
    BulkImportRequest,
    BulkImportResponse,
    BulkLeadStatusUpdate,
    EnrichRequest,
    EnrichResponse,
    LeadResponse,
    LeadUpdate,
    OutreachGenerateRequest,
    OutreachGenerateResponse,
    OutreachMessageResponse,
    PipelineStats,
    ScoreRequest,
    ScoreResponse,
    SearchResponse,
)
from src.services.apollo_client import ApolloClient
from src.services.lead_service import (
    enrich_leads,
    get_pipeline_stats,
    search_and_store_leads,
)

router = APIRouter(prefix="/api/leads", tags=["leads"])


@router.post("/import", response_model=BulkImportResponse)
async def import_leads(
    req: BulkImportRequest,
    db: Session = Depends(get_db),
    _key: str = Depends(verify_api_key),
) -> BulkImportResponse:
    """Bulk import leads into a campaign (bypasses Apollo)."""
    from src.models.lead import Campaign

    campaign = db.query(Campaign).filter(Campaign.id == req.campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    lead_ids: list[str] = []
    for lead_data in req.leads:
        lead_id = str(uuid.uuid4())
        lead = Lead(
            id=lead_id,
            first_name=lead_data.first_name,
            last_name=lead_data.last_name,
            email=lead_data.email,
            email_status=lead_data.email_status,
            phone=lead_data.phone,
            linkedin_url=lead_data.linkedin_url,
            title=lead_data.title,
            seniority=lead_data.seniority,
            department=lead_data.department,
            headline=lead_data.headline,
            company_name=lead_data.company_name,
            company_domain=lead_data.company_domain,
            company_industry=lead_data.company_industry,
            company_size=lead_data.company_size,
            company_revenue=lead_data.company_revenue,
            company_location=lead_data.company_location,
            source="import",
            status="new",
            campaign_id=req.campaign_id,
        )
        db.add(lead)
        lead_ids.append(lead_id)

    campaign.total_leads = (
        db.query(Lead).filter(Lead.campaign_id == req.campaign_id).count() + len(lead_ids)
    )
    db.commit()

    return BulkImportResponse(
        imported=len(lead_ids),
        campaign_id=req.campaign_id,
        lead_ids=lead_ids,
    )


@router.post("/search", response_model=SearchResponse)
async def search_leads(
    req: ApolloSearchRequest,
    db: Session = Depends(get_db),
    _key: str = Depends(verify_api_key),
) -> SearchResponse:
    """Search Apollo.io for leads and store them."""
    apollo = ApolloClient()
    leads, total = await search_and_store_leads(
        db=db,
        apollo=apollo,
        campaign_id=req.campaign_id,
        person_titles=req.person_titles,
        person_seniorities=req.person_seniorities,
        q_organization_domains=req.q_organization_domains,
        organization_industry_tag_ids=req.organization_industry_tag_ids,
        organization_num_employees_ranges=req.organization_num_employees_ranges,
        person_locations=req.person_locations,
        q_keywords=req.q_keywords,
        page=req.page,
        per_page=req.per_page,
    )
    return SearchResponse(
        leads=[LeadResponse.model_validate(lead) for lead in leads],
        total_found=total,
        page=req.page,
        per_page=req.per_page,
        campaign_id=req.campaign_id,
    )


@router.post("/enrich", response_model=EnrichResponse)
async def enrich(
    req: EnrichRequest,
    db: Session = Depends(get_db),
    _key: str = Depends(verify_api_key),
) -> EnrichResponse:
    """Enrich leads with full Apollo.io data (costs credits)."""
    apollo = ApolloClient()
    enriched_count, failed_count, leads = await enrich_leads(
        db=db,
        apollo=apollo,
        lead_ids=req.lead_ids,
    )
    return EnrichResponse(
        enriched=enriched_count,
        failed=failed_count,
        leads=[LeadResponse.model_validate(lead) for lead in leads],
    )


@router.post("/score", response_model=ScoreResponse)
async def score_leads_endpoint(
    req: ScoreRequest,
    db: Session = Depends(get_db),
    _key: str = Depends(verify_api_key),
) -> ScoreResponse:
    """Score leads using AI."""
    from langchain_core.language_models import BaseChatModel

    from src.scoring.lead_scorer import score_leads_batch
    from src.utils.llm import get_llm

    llm = get_llm()

    # Get leads to score
    query = db.query(Lead)
    if req.lead_ids:
        query = query.filter(Lead.id.in_(req.lead_ids))
    elif req.campaign_id:
        query = query.filter(Lead.campaign_id == req.campaign_id)
    else:
        # Score all unscored leads
        query = query.filter(Lead.score == 0)

    leads = query.all()
    if not leads:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No leads found to score")

    # Build ICP from campaign if available
    icp = None
    if req.campaign_id:
        from src.models.lead import Campaign

        campaign = db.query(Campaign).filter(Campaign.id == req.campaign_id).first()
        if campaign:
            icp = {
                "target_titles": campaign.target_titles,
                "target_industries": campaign.target_industries,
                "target_seniority": campaign.target_seniority,
                "min_employees": campaign.min_employees,
                "max_employees": campaign.max_employees,
            }

    results = await score_leads_batch(leads, llm, icp)

    for lead, score, reason in results:
        lead.score = score
        lead.score_reason = reason
        if lead.status in ("new", "enriched"):
            lead.status = "scored"

    db.commit()

    scored_leads = [lead for lead, _, _ in results]
    return ScoreResponse(
        scored=len(scored_leads),
        leads=[LeadResponse.model_validate(lead) for lead in scored_leads],
    )


@router.get("", response_model=list[LeadResponse])
async def list_leads(
    campaign_id: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    min_score: int = Query(0),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    _key: str = Depends(verify_api_key),
) -> list[Lead]:
    """List leads with filters."""
    query = db.query(Lead)
    if campaign_id:
        query = query.filter(Lead.campaign_id == campaign_id)
    if status_filter:
        query = query.filter(Lead.status == status_filter)
    if min_score > 0:
        query = query.filter(Lead.score >= min_score)

    return (
        query.order_by(Lead.score.desc(), Lead.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.patch("/bulk-status", response_model=list[LeadResponse])
async def bulk_update_status(
    req: BulkLeadStatusUpdate,
    db: Session = Depends(get_db),
    _key: str = Depends(verify_api_key),
) -> list[Lead]:
    """Update status for multiple leads at once."""
    valid_statuses = {"new", "enriched", "scored", "contacted", "qualified", "converted", "lost"}
    if req.status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {', '.join(sorted(valid_statuses))}",
        )

    leads = db.query(Lead).filter(Lead.id.in_(req.lead_ids)).all()
    if not leads:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No leads found")

    for lead in leads:
        lead.status = req.status
    db.commit()

    for lead in leads:
        db.refresh(lead)
    return leads


@router.get("/stats", response_model=PipelineStats)
async def pipeline_stats(
    db: Session = Depends(get_db),
    _key: str = Depends(verify_api_key),
) -> PipelineStats:
    """Get pipeline statistics."""
    return get_pipeline_stats(db)


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: str,
    db: Session = Depends(get_db),
    _key: str = Depends(verify_api_key),
) -> Lead:
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return lead


@router.patch("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: str,
    req: LeadUpdate,
    db: Session = Depends(get_db),
    _key: str = Depends(verify_api_key),
) -> Lead:
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    update_data = req.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(lead, field, value)
    db.commit()
    db.refresh(lead)
    return lead


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead(
    lead_id: str,
    db: Session = Depends(get_db),
    _key: str = Depends(verify_api_key),
) -> None:
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    db.delete(lead)
    db.commit()
