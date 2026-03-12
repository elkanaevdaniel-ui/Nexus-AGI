"""CRM Deal management API routes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.auth import verify_api_key
from src.database import get_db
from src.models.lead import CRMDeal, Lead
from src.schemas import DealCreate, DealResponse, DealUpdate

router = APIRouter(prefix="/api/deals", tags=["deals"])


@router.post("", response_model=DealResponse)
async def create_deal(
    req: DealCreate,
    db: Session = Depends(get_db),
    _key: str = Depends(verify_api_key),
) -> CRMDeal:
    """Create a CRM deal for a lead."""
    lead = db.query(Lead).filter(Lead.id == req.lead_id).first()
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    existing = db.query(CRMDeal).filter(CRMDeal.lead_id == req.lead_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Deal already exists for this lead",
        )

    deal = CRMDeal(
        id=str(uuid.uuid4()),
        lead_id=req.lead_id,
        title=req.title,
        value=req.value,
        currency=req.currency,
        stage=req.stage,
        notes=req.notes,
    )
    db.add(deal)

    if lead.status in ("new", "enriched", "scored", "contacted"):
        lead.status = "qualified"

    db.commit()
    db.refresh(deal)
    return deal


@router.get("", response_model=list[DealResponse])
async def list_deals(
    stage: str | None = Query(None),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    _key: str = Depends(verify_api_key),
) -> list[CRMDeal]:
    query = db.query(CRMDeal)
    if stage:
        query = query.filter(CRMDeal.stage == stage)
    return query.order_by(CRMDeal.updated_at.desc()).limit(limit).all()


@router.get("/{deal_id}", response_model=DealResponse)
async def get_deal(
    deal_id: str,
    db: Session = Depends(get_db),
    _key: str = Depends(verify_api_key),
) -> CRMDeal:
    deal = db.query(CRMDeal).filter(CRMDeal.id == deal_id).first()
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    return deal


@router.patch("/{deal_id}", response_model=DealResponse)
async def update_deal(
    deal_id: str,
    req: DealUpdate,
    db: Session = Depends(get_db),
    _key: str = Depends(verify_api_key),
) -> CRMDeal:
    deal = db.query(CRMDeal).filter(CRMDeal.id == deal_id).first()
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")

    update_data = req.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(deal, field, value)

    # Update lead status based on deal stage
    if "stage" in update_data:
        lead = db.query(Lead).filter(Lead.id == deal.lead_id).first()
        if lead:
            if deal.stage == "closed_won":
                lead.status = "converted"
            elif deal.stage == "closed_lost":
                lead.status = "lost"

    db.commit()
    db.refresh(deal)
    return deal
