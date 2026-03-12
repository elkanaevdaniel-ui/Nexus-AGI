"""Tests for outreach message API — including draft editing."""

import uuid

import pytest
from src.models.lead import OutreachMessage


@pytest.fixture
def sample_draft(db_session, sample_lead, sample_campaign):
    """Create a sample outreach draft."""
    msg = OutreachMessage(
        id=str(uuid.uuid4()),
        lead_id=sample_lead.id,
        campaign_id=sample_campaign.id,
        channel="email",
        subject="Quick question about TechCorp",
        body="Hi John, I noticed you're the CTO at TechCorp...",
        status="draft",
    )
    db_session.add(msg)
    db_session.commit()
    return msg


def test_list_outreach_messages(client, sample_draft):
    response = client.get("/api/outreach")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


def test_list_outreach_by_campaign_id(client, sample_draft, sample_campaign):
    response = client.get(f"/api/outreach?campaign_id={sample_campaign.id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["lead_id"] == sample_draft.lead_id


def test_list_outreach_by_campaign_id_empty(client, sample_draft):
    response = client.get("/api/outreach?campaign_id=nonexistent")
    assert response.status_code == 200
    assert len(response.json()) == 0


def test_get_outreach_message(client, sample_draft):
    response = client.get(f"/api/outreach/{sample_draft.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["subject"] == "Quick question about TechCorp"


def test_update_draft_subject(client, sample_draft):
    response = client.patch(
        f"/api/outreach/{sample_draft.id}",
        json={"subject": "Updated subject line"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["subject"] == "Updated subject line"
    assert data["body"] == sample_draft.body  # body unchanged


def test_update_draft_body(client, sample_draft):
    response = client.patch(
        f"/api/outreach/{sample_draft.id}",
        json={"body": "Completely rewritten body text."},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["body"] == "Completely rewritten body text."


def test_update_draft_both(client, sample_draft):
    response = client.patch(
        f"/api/outreach/{sample_draft.id}",
        json={"subject": "New subject", "body": "New body"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["subject"] == "New subject"
    assert data["body"] == "New body"


def test_update_sent_message_fails(client, db_session, sample_draft):
    sample_draft.status = "sent"
    db_session.commit()

    response = client.patch(
        f"/api/outreach/{sample_draft.id}",
        json={"body": "Should not work"},
    )
    assert response.status_code == 409


def test_update_nonexistent_message(client):
    response = client.patch(
        "/api/outreach/nonexistent",
        json={"body": "Does not matter"},
    )
    assert response.status_code == 404


def test_delete_outreach_message(client, sample_draft):
    response = client.delete(f"/api/outreach/{sample_draft.id}")
    assert response.status_code == 204

    response = client.get(f"/api/outreach/{sample_draft.id}")
    assert response.status_code == 404
