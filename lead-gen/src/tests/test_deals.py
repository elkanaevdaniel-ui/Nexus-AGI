"""Tests for CRM deal management API."""

import pytest


def test_create_deal(client, sample_lead):
    response = client.post(
        "/api/deals",
        json={
            "lead_id": sample_lead.id,
            "title": "TechCorp - Enterprise Plan",
            "value": 50000.0,
            "stage": "discovery",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "TechCorp - Enterprise Plan"
    assert data["value"] == 50000.0
    assert data["stage"] == "discovery"


def test_create_deal_duplicate(client, sample_lead):
    # Create first deal
    client.post(
        "/api/deals",
        json={"lead_id": sample_lead.id, "title": "Deal 1", "value": 1000},
    )
    # Try to create duplicate
    response = client.post(
        "/api/deals",
        json={"lead_id": sample_lead.id, "title": "Deal 2", "value": 2000},
    )
    assert response.status_code == 409


def test_create_deal_invalid_lead(client):
    response = client.post(
        "/api/deals",
        json={"lead_id": "nonexistent", "title": "Bad Deal", "value": 0},
    )
    assert response.status_code == 404


def test_list_deals(client, sample_lead):
    client.post(
        "/api/deals",
        json={"lead_id": sample_lead.id, "title": "Test Deal", "value": 10000},
    )
    response = client.get("/api/deals")
    assert response.status_code == 200
    assert len(response.json()) >= 1


def test_update_deal_stage(client, sample_lead, db_session):
    # Create deal
    resp = client.post(
        "/api/deals",
        json={"lead_id": sample_lead.id, "title": "Closing Deal", "value": 25000},
    )
    deal_id = resp.json()["id"]

    # Update to closed_won
    response = client.patch(
        f"/api/deals/{deal_id}",
        json={"stage": "closed_won", "probability": 100},
    )
    assert response.status_code == 200
    assert response.json()["stage"] == "closed_won"

    # Check lead status updated to converted
    lead_resp = client.get(f"/api/leads/{sample_lead.id}")
    assert lead_resp.json()["status"] == "converted"
