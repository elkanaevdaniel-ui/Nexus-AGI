"""Campaign pipeline orchestrator — runs search → score → enrich → draft."""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.models.lead import Campaign, Lead
from src.services.apollo_client import ApolloClient
from src.services.lead_service import enrich_leads, search_and_store_leads
from src.scoring.lead_scorer import score_leads_batch
from src.outreach.message_generator import generate_batch
from src.utils.llm import get_llm

logger = logging.getLogger(__name__)


def _update_stage(db: Session, campaign: Campaign, stage: str) -> None:
    """Update campaign pipeline stage."""
    campaign.pipeline_stage = stage
    db.commit()
    logger.info("Campaign %s → stage: %s", campaign.id, stage)


async def run_campaign_pipeline(
    campaign_id: str,
    enrich_top_n: int = 20,
    min_score_for_enrichment: int = 60,
) -> None:
    """
    Execute the full campaign pipeline as a background task.

    Creates its own DB session to avoid using a request-scoped session
    that may be closed before the task completes.

    Stages: searching → scoring → enriching → drafting → complete

    Args:
        campaign_id: The campaign to process.
        enrich_top_n: Max leads to enrich (controls Apollo credit spend).
        min_score_for_enrichment: Minimum score threshold for enrichment.
    """
    from src.database import SessionLocal

    db = SessionLocal()
    apollo = None
    try:
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign:
            logger.error("Campaign %s not found", campaign_id)
            return

        # Stage 1: Search for leads
        _update_stage(db, campaign, "searching")

        # Check if leads were pre-imported (manual/import source)
        existing_leads = (
            db.query(Lead)
            .filter(Lead.campaign_id == campaign_id)
            .all()
        )

        all_leads: list[Lead] = []

        if existing_leads:
            # Use pre-imported leads — skip Apollo search
            all_leads = existing_leads
            logger.info(
                "Campaign %s: using %d pre-imported leads, skipping Apollo search",
                campaign_id, len(all_leads),
            )
        else:
            # Search Apollo for new leads
            apollo = ApolloClient()
            if not apollo._api_key:
                logger.error("APOLLO_API_KEY is not set — cannot search leads")
                _update_stage(db, campaign, "failed")
                return

            search_params: dict = {}
            if campaign.parsed_filters:
                filters = json.loads(campaign.parsed_filters)
                if filters.get("person_titles"):
                    search_params["person_titles"] = filters["person_titles"]
                if filters.get("person_seniorities"):
                    search_params["person_seniorities"] = filters["person_seniorities"]
                if filters.get("person_locations"):
                    search_params["person_locations"] = filters["person_locations"]
                if filters.get("keywords"):
                    search_params["q_keywords"] = " ".join(filters["keywords"])
                if filters.get("min_employees") and filters.get("max_employees"):
                    search_params["organization_num_employees_ranges"] = [
                        f"{filters['min_employees']},{filters['max_employees']}"
                    ]
            else:
                if campaign.target_titles:
                    search_params["person_titles"] = [
                        t.strip() for t in campaign.target_titles.split(",")
                    ]
                if campaign.target_seniority:
                    search_params["person_seniorities"] = [
                        s.strip() for s in campaign.target_seniority.split(",")
                    ]
                if campaign.target_locations:
                    search_params["person_locations"] = [
                        l.strip() for l in campaign.target_locations.split(",")
                    ]
                if campaign.keywords:
                    search_params["q_keywords"] = campaign.keywords
                if campaign.min_employees and campaign.max_employees:
                    search_params["organization_num_employees_ranges"] = [
                        f"{campaign.min_employees},{campaign.max_employees}"
                    ]

            for page in range(1, 4):
                search_params["page"] = page
                search_params["per_page"] = 25
                leads, total = await search_and_store_leads(
                    db=db,
                    apollo=apollo,
                    campaign_id=campaign_id,
                    **search_params,
                )
                all_leads.extend(leads)
                if len(all_leads) >= total or len(leads) == 0:
                    break

        if not all_leads:
            _update_stage(db, campaign, "complete")
            return

        # Stage 2: Score leads
        _update_stage(db, campaign, "scoring")
        llm = get_llm()

        icp = {
            "target_titles": campaign.target_titles,
            "target_industries": campaign.target_industries,
            "target_seniority": campaign.target_seniority,
            "min_employees": campaign.min_employees,
            "max_employees": campaign.max_employees,
        }

        results = await score_leads_batch(all_leads, llm, icp)
        for lead, score, reason in results:
            lead.score = score
            lead.score_reason = reason
            if lead.status == "new":
                lead.status = "scored"
        db.commit()

        # Stage 3: Enrich top-scored leads
        _update_stage(db, campaign, "enriching")
        top_leads = sorted(all_leads, key=lambda l: l.score, reverse=True)
        leads_to_enrich = [
            l for l in top_leads
            if l.score >= min_score_for_enrichment
        ][:enrich_top_n]

        if leads_to_enrich:
            # Check if we have Apollo available for enrichment
            has_apollo = apollo is not None and apollo._api_key
            if has_apollo:
                lead_ids = [l.id for l in leads_to_enrich]
                await enrich_leads(db=db, apollo=apollo, lead_ids=lead_ids)
            else:
                # For imported leads without Apollo, mark as enriched directly
                for lead in leads_to_enrich:
                    if lead.status in ("new", "scored"):
                        lead.status = "enriched"
                db.commit()
                logger.info(
                    "No Apollo key — marked %d imported leads as enriched",
                    len(leads_to_enrich),
                )

            campaign.enriched_leads = (
                db.query(Lead)
                .filter(Lead.campaign_id == campaign_id, Lead.status == "enriched")
                .count()
            )
            db.commit()

        # Stage 4: Generate outreach drafts for enriched leads
        _update_stage(db, campaign, "drafting")
        enriched = (
            db.query(Lead)
            .filter(Lead.campaign_id == campaign_id, Lead.status == "enriched")
            .all()
        )

        if enriched:
            from src.models.lead import OutreachMessage
            import uuid

            messages_data = await generate_batch(
                leads=enriched,
                llm=llm,
                channel="email",
                tone="professional",
            )

            for msg_data in messages_data:
                msg = OutreachMessage(
                    id=msg_data["id"],
                    lead_id=msg_data["lead_id"],
                    campaign_id=campaign_id,
                    channel="email",
                    subject=msg_data.get("subject"),
                    body=msg_data["body"],
                    status="draft",
                )
                db.add(msg)
            db.commit()

        # Complete
        _update_stage(db, campaign, "complete")
        campaign.total_leads = (
            db.query(Lead).filter(Lead.campaign_id == campaign_id).count()
        )
        db.commit()

    except Exception as e:
        logger.exception("Pipeline failed for campaign %s: %s", campaign_id, e)
        try:
            campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
            if campaign:
                campaign.pipeline_stage = "failed"
                db.commit()
                logger.info("Campaign %s → stage: failed", campaign_id)
        except Exception:
            logger.exception("Failed to update campaign stage to 'failed'")
    finally:
        try:
            if apollo:
                await apollo.close()
        except Exception:
            pass
        db.close()
