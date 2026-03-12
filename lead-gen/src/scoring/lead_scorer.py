"""AI-powered lead scoring using LangGraph + Claude."""

import asyncio
import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models import BaseChatModel

from src.models.lead import Lead

logger = logging.getLogger(__name__)


SCORING_SYSTEM_PROMPT = """You are a B2B SaaS lead scoring expert. Given a lead's profile, score them 0-100 based on how well they match the Ideal Customer Profile (ICP).

## Scoring Criteria (B2B SaaS):

**Title & Seniority (0-30 points)**
- C-Suite / Founder / VP: 25-30
- Director / Head of: 18-24
- Manager / Senior: 10-17
- Individual Contributor: 0-9

**Company Fit (0-30 points)**
- Industry match: 0-10
- Company size in range: 0-10
- Revenue/funding signals: 0-10

**Contact Quality (0-20 points)**
- Verified business email: 15-20
- Guessed email: 5-14
- No email: 0-4

**Engagement Signals (0-20 points)**
- Has LinkedIn profile: +5
- Has phone number: +5
- Department relevance: +10

## Output Format
Respond with ONLY valid JSON:
{
  "score": <0-100>,
  "reason": "<1-2 sentence explanation>"
}"""


def build_lead_prompt(lead: Lead, icp: dict | None = None) -> str:
    """Build the scoring prompt for a single lead."""
    icp_section = ""
    if icp:
        icp_section = f"\n\n## Target ICP:\n{json.dumps(icp, indent=2)}"

    return f"""Score this lead:
{icp_section}

## Lead Profile:
- Name: {lead.first_name} {lead.last_name}
- Title: {lead.title or 'Unknown'}
- Seniority: {lead.seniority or 'Unknown'}
- Department: {lead.department or 'Unknown'}
- Company: {lead.company_name or 'Unknown'}
- Industry: {lead.company_industry or 'Unknown'}
- Company Size: {lead.company_size or 'Unknown'} employees
- Revenue: {lead.company_revenue or 'Unknown'}
- Location: {lead.company_location or 'Unknown'}
- Email: {'Yes - ' + (lead.email_status or 'unknown status') if lead.email else 'No'}
- Phone: {'Yes' if lead.phone else 'No'}
- LinkedIn: {'Yes' if lead.linkedin_url else 'No'}"""


async def score_lead(
    lead: Lead,
    llm: BaseChatModel,
    icp: dict | None = None,
) -> tuple[int, str]:
    """
    Score a single lead using AI.

    Returns (score, reason) tuple.
    """
    messages = [
        SystemMessage(content=SCORING_SYSTEM_PROMPT),
        HumanMessage(content=build_lead_prompt(lead, icp)),
    ]

    response = await llm.ainvoke(messages)
    content = response.content

    try:
        # Extract JSON from response
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        result = json.loads(content.strip())
        score = max(0, min(100, int(result.get("score", 0))))
        reason = result.get("reason", "No reason provided")
    except (json.JSONDecodeError, ValueError, IndexError):
        logger.warning(
            "Failed to parse scoring response for lead %s %s: %s",
            lead.first_name, lead.last_name, content[:200],
        )
        score = 0
        reason = "Scoring failed: could not parse LLM response"

    return score, reason


async def score_leads_batch(
    leads: list[Lead],
    llm: BaseChatModel,
    icp: dict | None = None,
    max_concurrency: int = 10,
) -> list[tuple[Lead, int, str]]:
    """Score multiple leads concurrently. Returns list of (lead, score, reason)."""
    semaphore = asyncio.Semaphore(max_concurrency)

    async def _score_with_limit(lead: Lead) -> tuple[Lead, int, str]:
        async with semaphore:
            score, reason = await score_lead(lead, llm, icp)
            return lead, score, reason

    return list(await asyncio.gather(*[_score_with_limit(l) for l in leads]))
