"""Tests for campaign management API."""

import pytest


def test_create_campaign(client):
    response = client.post(
        "/api/campaigns",
        json={
            "name": "SaaS Founders",
            "target_titles": "CEO,Founder,CTO",
            "target_industries": "technology",
            "min_employees": 10,
            "max_employees": 200,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "SaaS Founders"
    assert data["status"] == "active"
    assert data["total_leads"] == 0


def test_list_campaigns(client, sample_campaign):
    response = client.get("/api/campaigns")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["name"] == sample_campaign.name


def test_get_campaign(client, sample_campaign):
    response = client.get(f"/api/campaigns/{sample_campaign.id}")
    assert response.status_code == 200
    assert response.json()["id"] == sample_campaign.id


def test_get_campaign_not_found(client):
    response = client.get("/api/campaigns/nonexistent")
    assert response.status_code == 404


def test_update_campaign(client, sample_campaign):
    response = client.patch(
        f"/api/campaigns/{sample_campaign.id}",
        json={"name": "Updated Campaign", "status": "paused"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Campaign"
    assert data["status"] == "paused"


def test_delete_campaign(client, sample_campaign):
    response = client.delete(f"/api/campaigns/{sample_campaign.id}")
    assert response.status_code == 204

    response = client.get(f"/api/campaigns/{sample_campaign.id}")
    assert response.status_code == 404
