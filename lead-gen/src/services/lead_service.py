"""Core business logic for lead management."""

import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models.lead import Campaign, CRMDeal, Lead, OutreachMessage
from src.schemas import PipelineStats
from src.services.apollo_client import ApolloClient, parse_apollo_person


async def search_and_store_leads(
    db: Session,
    apollo: ApolloClient,
    campaign_id: str | None = None,
    **search_params: object,
) -> tuple[list[Lead], int]:
    """
    Search Apollo.io and store results as leads.

    Returns (leads, total_found).
    """
    result = await apollo.search_people(**search_params)
    people = result.get("people") or []
    total = result.get("pagination", {}).get("total_entries", len(people))

    leads = []
    for person_data in people:
        apollo_id = person_data.get("id")

        # Skip if we already have this lead
        existing = db.query(Lead).filter(Lead.apollo_id == apollo_id).first()
        if existing:
            leads.append(existing)
            continue

        lead_data = parse_apollo_person(person_data)
        if campaign_id:
            lead_data["campaign_id"] = campaign_id

        lead = Lead(**lead_data)
        db.add(lead)
        leads.append(lead)

    db.commit()

    # Update campaign stats
    if campaign_id:
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if campaign:
            campaign.total_leads = (
                db.query(Lead).filter(Lead.campaign_id == campaign_id).count()
            )
            db.commit()

    return leads, total


async def enrich_leads(
    db: Session,
    apollo: ApolloClient,
    lead_ids: list[str],
) -> tuple[int, int, list[Lead]]:
    """
    Enrich leads with full Apollo.io data.

    Returns (enriched_count, failed_count, leads).
    """
    enriched = 0
    failed = 0
    leads = []

    for lead_id in lead_ids:
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            failed += 1
            continue

        try:
            data = await apollo.enrich_person(
                apollo_id=lead.apollo_id,
                first_name=lead.first_name,
                last_name=lead.last_name,
                organization_name=lead.company_name,
            )
            person = data.get("person") or data
            if person:
                lead.email = person.get("email") or lead.email
                lead.email_status = person.get("email_status") or lead.email_status
                phones = person.get("phone_numbers") or []
                if phones:
                    lead.phone = phones[0].get("number")
                lead.linkedin_url = person.get("linkedin_url") or lead.linkedin_url
                lead.title = person.get("title") or lead.title
                lead.seniority = person.get("seniority") or lead.seniority
                lead.headline = person.get("headline") or lead.headline

                org = person.get("organization") or {}
                lead.company_domain = org.get("website_url") or lead.company_domain
                lead.company_industry = org.get("industry") or lead.company_industry
                lead.company_size = org.get("estimated_num_employees") or lead.company_size

                lead.status = "enriched"
                enriched += 1
            else:
                failed += 1
        except Exception:
            failed += 1

        leads.append(lead)

    db.commit()
    return enriched, failed, leads


def get_pipeline_stats(db: Session) -> PipelineStats:
    """Get pipeline statistics across all leads."""
    total = db.query(Lead).count()

    status_counts: dict[str, int] = {}
    for status_name in ["new", "enriched", "scored", "contacted", "qualified", "converted", "lost"]:
        status_counts[status_name] = (
            db.query(Lead).filter(Lead.status == status_name).count()
        )

    total_deals = (
        db.query(func.coalesce(func.sum(CRMDeal.value), 0.0)).scalar() or 0.0
    )
    avg_score = db.query(func.coalesce(func.avg(Lead.score), 0.0)).scalar() or 0.0

    return PipelineStats(
        total_leads=total,
        new=status_counts["new"],
        enriched=status_counts["enriched"],
        scored=status_counts["scored"],
        contacted=status_counts["contacted"],
        qualified=status_counts["qualified"],
        converted=status_counts["converted"],
        lost=status_counts["lost"],
        total_deals_value=float(total_deals),
        avg_score=float(avg_score),
    )
