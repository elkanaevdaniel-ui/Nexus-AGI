"""Test fixtures for Lead Gen service."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.auth import verify_api_key
from src.database import Base, get_db
from src.main import app
from src.models.lead import Campaign, CRMDeal, Lead, OutreachMessage

TEST_API_KEY = "test-api-key-for-tests"


@pytest.fixture
def db_session():
    """Create a fresh in-memory database for each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    """FastAPI test client with overridden DB dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    async def override_verify_api_key() -> str:
        return TEST_API_KEY

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[verify_api_key] = override_verify_api_key
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def sample_campaign(db_session) -> Campaign:
    """Create a sample campaign."""
    campaign = Campaign(
        id=str(uuid.uuid4()),
        name="Test B2B SaaS Campaign",
        description="Testing lead gen",
        target_titles="CTO,VP Engineering",
        target_industries="technology",
        target_seniority="director,vp,c_suite",
        min_employees=10,
        max_employees=500,
    )
    db_session.add(campaign)
    db_session.commit()
    return campaign


@pytest.fixture
def sample_lead(db_session, sample_campaign) -> Lead:
    """Create a sample lead."""
    lead = Lead(
        id=str(uuid.uuid4()),
        apollo_id="apollo_test_123",
        first_name="John",
        last_name="Doe",
        email="john@example.com",
        email_status="verified",
        title="CTO",
        seniority="c_suite",
        department="engineering",
        company_name="TechCorp",
        company_domain="techcorp.com",
        company_industry="technology",
        company_size=150,
        company_location="San Francisco, CA, US",
        source="apollo",
        status="enriched",
        campaign_id=sample_campaign.id,
    )
    db_session.add(lead)
    db_session.commit()
    return lead
