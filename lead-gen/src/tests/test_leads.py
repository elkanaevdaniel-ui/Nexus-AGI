"""Tests for lead management API."""

import pytest


def test_list_leads(client, sample_lead):
    response = client.get("/api/leads")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["first_name"] == "John"


def test_list_leads_with_filters(client, sample_lead):
    # Filter by status
    response = client.get("/api/leads?status=enriched")
    assert response.status_code == 200
    assert len(response.json()) >= 1

    # Filter by min_score
    response = client.get("/api/leads?min_score=100")
    assert response.status_code == 200
    assert len(response.json()) == 0


def test_get_lead(client, sample_lead):
    response = client.get(f"/api/leads/{sample_lead.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "john@example.com"
    assert data["company_name"] == "TechCorp"


def test_get_lead_not_found(client):
    response = client.get("/api/leads/nonexistent")
    assert response.status_code == 404


def test_update_lead(client, sample_lead):
    response = client.patch(
        f"/api/leads/{sample_lead.id}",
        json={"status": "qualified", "score": 85},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "qualified"
    assert data["score"] == 85


def test_delete_lead(client, sample_lead):
    response = client.delete(f"/api/leads/{sample_lead.id}")
    assert response.status_code == 204

    response = client.get(f"/api/leads/{sample_lead.id}")
    assert response.status_code == 404


def test_bulk_update_status(client, sample_lead):
    response = client.patch(
        "/api/leads/bulk-status",
        json={"lead_ids": [sample_lead.id], "status": "qualified"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["status"] == "qualified"


def test_bulk_update_status_invalid(client, sample_lead):
    response = client.patch(
        "/api/leads/bulk-status",
        json={"lead_ids": [sample_lead.id], "status": "invalid_status"},
    )
    assert response.status_code == 400


def test_pipeline_stats(client, sample_lead):
    response = client.get("/api/leads/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_leads"] >= 1
    assert "enriched" in data
    assert "total_deals_value" in data
