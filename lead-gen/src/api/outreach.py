"""Outreach message generation and management API routes."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.auth import verify_api_key
from src.database import get_db
from src.models.lead import Lead, OutreachMessage
from src.outreach.message_generator import generate_batch
from src.schemas import (
    OutreachGenerateRequest,
    OutreachGenerateResponse,
    OutreachMessageResponse,
    OutreachSendRequest,
    OutreachSendResponse,
    OutreachUpdateRequest,
)
from src.utils.llm import get_llm

router = APIRouter(prefix="/api/outreach", tags=["outreach"])


@router.post("/generate", response_model=OutreachGenerateResponse)
async def generate_messages(
    req: OutreachGenerateRequest,
    db: Session = Depends(get_db),
    _key: str = Depends(verify_api_key),
) -> OutreachGenerateResponse:
    """Generate personalized outreach messages for leads using AI."""
    leads = db.query(Lead).filter(Lead.id.in_(req.lead_ids)).all()
    if not leads:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No leads found",
        )

    llm = get_llm()
    generated = await generate_batch(
        leads=leads,
        llm=llm,
        channel=req.channel,
        tone=req.tone,
        custom_instructions=req.custom_instructions,
    )

    messages = []
    for msg_data in generated:
        msg = OutreachMessage(
            id=msg_data["id"],
            lead_id=msg_data["lead_id"],
            channel=req.channel,
            subject=msg_data.get("subject"),
            body=msg_data["body"],
            status="draft",
        )
        db.add(msg)
        messages.append(msg)

    db.commit()
    for msg in messages:
        db.refresh(msg)

    return OutreachGenerateResponse(
        messages=[OutreachMessageResponse.model_validate(m) for m in messages],
    )


@router.post("/send", response_model=OutreachSendResponse)
async def send_messages(
    req: OutreachSendRequest,
    db: Session = Depends(get_db),
    _key: str = Depends(verify_api_key),
) -> OutreachSendResponse:
    """
    Mark messages as sent.

    In a production setup, this would integrate with Apollo sequences
    or an email sending service. For now, it marks messages as sent
    and updates lead status.
    """
    sent = 0
    failed = 0

    for msg_id in req.message_ids:
        msg = db.query(OutreachMessage).filter(OutreachMessage.id == msg_id).first()
        if not msg:
            failed += 1
            continue

        msg.status = "sent"
        msg.sent_at = datetime.now(timezone.utc)

        # Update lead status
        lead = db.query(Lead).filter(Lead.id == msg.lead_id).first()
        if lead and lead.status in ("new", "enriched", "scored"):
            lead.status = "contacted"

        sent += 1

    db.commit()
    return OutreachSendResponse(sent=sent, failed=failed)


@router.patch("/{message_id}", response_model=OutreachMessageResponse)
async def update_message(
    message_id: str,
    req: OutreachUpdateRequest,
    db: Session = Depends(get_db),
    _key: str = Depends(verify_api_key),
) -> OutreachMessage:
    """Edit an outreach message draft (subject and/or body)."""
    msg = db.query(OutreachMessage).filter(OutreachMessage.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    if msg.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only draft messages can be edited",
        )

    update_data = req.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(msg, field, value)
    db.commit()
    db.refresh(msg)
    return msg


@router.get("", response_model=list[OutreachMessageResponse])
async def list_messages(
    lead_id: str | None = Query(None),
    campaign_id: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    _key: str = Depends(verify_api_key),
) -> list[OutreachMessage]:
    """List outreach messages with filters."""
    query = db.query(OutreachMessage)
    if lead_id:
        query = query.filter(OutreachMessage.lead_id == lead_id)
    if campaign_id:
        query = query.filter(OutreachMessage.campaign_id == campaign_id)
    if status_filter:
        query = query.filter(OutreachMessage.status == status_filter)

    return query.order_by(OutreachMessage.created_at.desc()).limit(limit).all()


@router.get("/{message_id}", response_model=OutreachMessageResponse)
async def get_message(
    message_id: str,
    db: Session = Depends(get_db),
    _key: str = Depends(verify_api_key),
) -> OutreachMessage:
    msg = db.query(OutreachMessage).filter(OutreachMessage.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    return msg


@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(
    message_id: str,
    db: Session = Depends(get_db),
    _key: str = Depends(verify_api_key),
) -> None:
    msg = db.query(OutreachMessage).filter(OutreachMessage.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    db.delete(msg)
    db.commit()
