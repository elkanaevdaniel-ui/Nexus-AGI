"""Campaign management API routes."""

import asyncio
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.auth import verify_api_key
from src.database import get_db
from src.models.lead import Campaign, Lead, OutreachMessage
from src.schemas import (
    CampaignCreate,
    CampaignCreateFromICP,
    CampaignResponse,
    CampaignUpdate,
    ICPParseRequest,
    ICPParseResponse,
    PipelineRunRequest,
    PipelineRunResponse,
    PipelineStatusResponse,
)

# Pipelines stuck longer than this are considered stale and auto-failed
STALE_PIPELINE_MINUTES = 10
_RUNNING_STAGES = {"searching", "scoring", "enriching", "drafting"}


def _auto_fail_stale_pipelines(db: Session) -> None:
    """Mark campaigns as failed if pipeline has been stuck for too long."""
    now = datetime.now(timezone.utc)
    running = (
        db.query(Campaign)
        .filter(Campaign.pipeline_stage.in_(_RUNNING_STAGES))
        .all()
    )
    changed = False
    for campaign in running:
        if not campaign.updated_at:
            continue
        updated = campaign.updated_at
        # SQLite may return naive datetimes — treat as UTC
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        if (now - updated).total_seconds() > STALE_PIPELINE_MINUTES * 60:
            campaign.pipeline_stage = "failed"
            changed = True
    if changed:
        db.commit()

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


@router.post("", response_model=CampaignResponse)
async def create_campaign(
    req: CampaignCreate,
    db: Session = Depends(get_db),
    _key: str = Depends(verify_api_key),
) -> Campaign:
    campaign = Campaign(
        id=str(uuid.uuid4()),
        name=req.name,
        description=req.description,
        icp_raw_text=req.icp_raw_text,
        parsed_filters=req.parsed_filters,
        target_titles=req.target_titles,
        target_industries=req.target_industries,
        target_seniority=req.target_seniority,
        target_locations=req.target_locations,
        min_employees=req.min_employees,
        max_employees=req.max_employees,
        keywords=req.keywords,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign


@router.post("/parse-icp", response_model=ICPParseResponse)
async def parse_icp_endpoint(
    req: ICPParseRequest,
    _key: str = Depends(verify_api_key),
) -> ICPParseResponse:
    """Parse natural language ICP into structured Apollo.io search filters."""
    from src.services.icp_parser import parse_icp
    from src.utils.llm import get_llm

    llm = get_llm()
    filters = await parse_icp(req.icp_text, llm)
    return ICPParseResponse(**filters.model_dump())


@router.post("/create-from-icp", response_model=CampaignResponse)
async def create_campaign_from_icp(
    req: CampaignCreateFromICP,
    db: Session = Depends(get_db),
    _key: str = Depends(verify_api_key),
) -> Campaign:
    """Create a campaign from natural language ICP and optionally auto-run pipeline."""
    from src.services.icp_parser import parse_icp
    from src.utils.llm import get_llm

    llm = get_llm()
    filters = await parse_icp(req.icp_text, llm)
    filters_dict = filters.model_dump()

    campaign = Campaign(
        id=str(uuid.uuid4()),
        name=req.name,
        icp_raw_text=req.icp_text,
        parsed_filters=json.dumps(filters_dict),
        target_titles=",".join(filters.person_titles) if filters.person_titles else None,
        target_industries=",".join(filters.organization_industries) if filters.organization_industries else None,
        target_seniority=",".join(filters.person_seniorities) if filters.person_seniorities else None,
        target_locations=",".join(filters.person_locations) if filters.person_locations else None,
        min_employees=filters.min_employees,
        max_employees=filters.max_employees,
        keywords=",".join(filters.keywords) if filters.keywords else None,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    if req.auto_run:
        from src.services.pipeline import run_campaign_pipeline

        asyncio.create_task(
            run_campaign_pipeline(
                campaign_id=campaign.id,
                enrich_top_n=req.enrich_top_n,
                min_score_for_enrichment=req.min_score_for_enrichment,
            )
        )

    return campaign


@router.post("/{campaign_id}/reset-pipeline", response_model=CampaignResponse)
async def reset_pipeline(
    campaign_id: str,
    db: Session = Depends(get_db),
    _key: str = Depends(verify_api_key),
) -> Campaign:
    """Reset a stuck or failed pipeline back to idle so it can be re-run."""
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    campaign.pipeline_stage = "idle"
    db.commit()
    db.refresh(campaign)
    return campaign


@router.post("/run-pipeline", response_model=PipelineRunResponse)
async def run_pipeline(
    req: PipelineRunRequest,
    db: Session = Depends(get_db),
    _key: str = Depends(verify_api_key),
) -> PipelineRunResponse:
    """Trigger the full campaign pipeline (search → score → enrich → draft)."""
    campaign = db.query(Campaign).filter(Campaign.id == req.campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    # Allow re-running idle, complete, failed, or stale pipelines
    if campaign.pipeline_stage in _RUNNING_STAGES:
        # Check if it's stale (stuck for too long) — allow re-run if so
        now = datetime.now(timezone.utc)
        updated = campaign.updated_at
        if updated and updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        if updated and (now - updated).total_seconds() < STALE_PIPELINE_MINUTES * 60:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Pipeline already running (stage: {campaign.pipeline_stage}). "
                       f"Wait {STALE_PIPELINE_MINUTES} min or reset it first.",
            )

    # Reset stage before re-running
    campaign.pipeline_stage = "searching"
    db.commit()

    from src.services.pipeline import run_campaign_pipeline

    asyncio.create_task(
        run_campaign_pipeline(
            campaign_id=campaign.id,
            enrich_top_n=req.enrich_top_n,
            min_score_for_enrichment=req.min_score_for_enrichment,
        )
    )

    return PipelineRunResponse(
        status="started",
        campaign_id=campaign.id,
        pipeline_stage="searching",
    )


@router.post("/{campaign_id}/reset-pipeline", response_model=PipelineRunResponse)
async def reset_pipeline(
    campaign_id: str,
    db: Session = Depends(get_db),
    _key: str = Depends(verify_api_key),
) -> PipelineRunResponse:
    """Reset a stuck or failed pipeline back to idle so it can be re-run."""
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    campaign.pipeline_stage = "idle"
    db.commit()
    return PipelineRunResponse(
        status="reset",
        campaign_id=campaign.id,
        pipeline_stage="idle",
    )


@router.get("/{campaign_id}/pipeline-status", response_model=PipelineStatusResponse)
async def get_pipeline_status(
    campaign_id: str,
    db: Session = Depends(get_db),
    _key: str = Depends(verify_api_key),
) -> PipelineStatusResponse:
    """Get current pipeline progress for a campaign."""
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    total_leads = db.query(Lead).filter(Lead.campaign_id == campaign_id).count()
    scored_leads = db.query(Lead).filter(
        Lead.campaign_id == campaign_id, Lead.score > 0
    ).count()
    enriched_leads = db.query(Lead).filter(
        Lead.campaign_id == campaign_id, Lead.status == "enriched"
    ).count()
    drafts_generated = db.query(OutreachMessage).filter(
        OutreachMessage.campaign_id == campaign_id
    ).count()

    return PipelineStatusResponse(
        campaign_id=campaign_id,
        pipeline_stage=campaign.pipeline_stage or "idle",
        total_leads=total_leads,
        scored_leads=scored_leads,
        enriched_leads=enriched_leads,
        drafts_generated=drafts_generated,
    )


@router.get("/{campaign_id}/export")
async def export_campaign(
    campaign_id: str,
    min_score: int = Query(0, ge=0, le=100),
    status_filter: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    _key: str = Depends(verify_api_key),
) -> StreamingResponse:
    """Export campaign leads as CSV."""
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    from src.services.export_service import export_leads_csv

    csv_content = export_leads_csv(
        db=db,
        campaign_id=campaign_id,
        min_score=min_score,
        status_filter=status_filter,
    )

    filename = f"{campaign.name.replace(' ', '_').lower()}_leads.csv"
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("", response_model=list[CampaignResponse])
async def list_campaigns(
    db: Session = Depends(get_db),
    _key: str = Depends(verify_api_key),
) -> list[Campaign]:
    _auto_fail_stale_pipelines(db)
    return db.query(Campaign).order_by(Campaign.created_at.desc()).all()


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: str,
    db: Session = Depends(get_db),
    _key: str = Depends(verify_api_key),
) -> Campaign:
    _auto_fail_stale_pipelines(db)
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return campaign


@router.patch("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: str,
    req: CampaignUpdate,
    db: Session = Depends(get_db),
    _key: str = Depends(verify_api_key),
) -> Campaign:
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    update_data = req.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(campaign, field, value)

    db.commit()
    db.refresh(campaign)
    return campaign


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(
    campaign_id: str,
    db: Session = Depends(get_db),
    _key: str = Depends(verify_api_key),
) -> None:
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    db.delete(campaign)
    db.commit()
