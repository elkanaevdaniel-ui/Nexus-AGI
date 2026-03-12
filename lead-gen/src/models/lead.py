"""SQLAlchemy ORM models for Lead Gen service."""

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from src.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Lead(Base):
    """A person discovered via Apollo.io or other sources."""

    __tablename__ = "leads"

    id = Column(String, primary_key=True)
    apollo_id = Column(String, unique=True, nullable=True, index=True)

    # Contact info
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, nullable=True, index=True)
    email_status = Column(String, nullable=True)  # verified / guessed / unavailable
    phone = Column(String, nullable=True)
    linkedin_url = Column(String, nullable=True)

    # Professional
    title = Column(String, nullable=True)
    seniority = Column(String, nullable=True)
    department = Column(String, nullable=True)
    headline = Column(String, nullable=True)

    # Company
    company_name = Column(String, nullable=True, index=True)
    company_domain = Column(String, nullable=True)
    company_industry = Column(String, nullable=True)
    company_size = Column(Integer, nullable=True)
    company_revenue = Column(String, nullable=True)
    company_location = Column(String, nullable=True)

    # Lead management
    source = Column(String, default="apollo")  # apollo / manual / import
    status = Column(String, default="new", index=True)  # new / enriched / scored / contacted / qualified / converted / lost
    score = Column(Integer, default=0)
    score_reason = Column(Text, nullable=True)

    # Campaign
    campaign_id = Column(String, ForeignKey("campaigns.id"), nullable=True, index=True)
    campaign = relationship("Campaign", back_populates="leads")

    # CRM
    deal = relationship("CRMDeal", back_populates="lead", uselist=False, cascade="all, delete-orphan")
    outreach_messages = relationship("OutreachMessage", back_populates="lead", cascade="all, delete-orphan")

    # Metadata
    raw_data = Column(Text, nullable=True)  # JSON dump from Apollo
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class Campaign(Base):
    """A lead generation campaign targeting a specific ICP."""

    __tablename__ = "campaigns"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    # ICP (Ideal Customer Profile)
    icp_raw_text = Column(Text, nullable=True)  # Original natural language ICP input
    parsed_filters = Column(Text, nullable=True)  # JSON of parsed Apollo filters
    target_titles = Column(Text, nullable=True)  # comma-separated
    target_industries = Column(Text, nullable=True)
    target_seniority = Column(Text, nullable=True)
    target_locations = Column(Text, nullable=True)
    min_employees = Column(Integer, nullable=True)
    max_employees = Column(Integer, nullable=True)
    keywords = Column(Text, nullable=True)

    # Status
    status = Column(String, default="active")  # active / paused / completed
    pipeline_stage = Column(String, default="idle")  # idle / searching / scoring / enriching / drafting / complete / failed
    total_leads = Column(Integer, default=0)
    enriched_leads = Column(Integer, default=0)
    contacted_leads = Column(Integer, default=0)

    leads = relationship("Lead", back_populates="campaign", cascade="all, delete-orphan")

    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class OutreachMessage(Base):
    """A message sent to a lead as part of an outreach sequence."""

    __tablename__ = "outreach_messages"

    id = Column(String, primary_key=True)
    lead_id = Column(String, ForeignKey("leads.id"), nullable=False, index=True)
    campaign_id = Column(String, ForeignKey("campaigns.id"), nullable=True, index=True)

    channel = Column(String, nullable=False)  # email / linkedin / apollo_sequence
    sequence_step = Column(Integer, default=1)
    subject = Column(String, nullable=True)
    body = Column(Text, nullable=False)
    status = Column(String, default="draft")  # draft / sent / delivered / opened / replied / bounced

    apollo_sequence_id = Column(String, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    opened_at = Column(DateTime, nullable=True)
    replied_at = Column(DateTime, nullable=True)

    lead = relationship("Lead", back_populates="outreach_messages")

    created_at = Column(DateTime, default=_utcnow)


class CRMDeal(Base):
    """Simple CRM deal tracker for qualified leads."""

    __tablename__ = "crm_deals"

    id = Column(String, primary_key=True)
    lead_id = Column(String, ForeignKey("leads.id"), nullable=False, unique=True, index=True)

    title = Column(String, nullable=False)
    value = Column(Float, default=0.0)
    currency = Column(String, default="USD")
    stage = Column(String, default="prospect")  # prospect / discovery / proposal / negotiation / closed_won / closed_lost
    probability = Column(Integer, default=10)
    notes = Column(Text, nullable=True)

    next_action = Column(String, nullable=True)
    next_action_date = Column(DateTime, nullable=True)

    lead = relationship("Lead", back_populates="deal")

    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
