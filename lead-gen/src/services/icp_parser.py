"""Parse natural language ICP descriptions into structured Apollo.io search filters."""

import json
import logging

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ICPFilters(BaseModel):
    """Structured Apollo.io search filters parsed from natural language."""

    person_titles: list[str] = []
    person_seniorities: list[str] = []
    person_locations: list[str] = []
    organization_industries: list[str] = []
    organization_locations: list[str] = []
    min_employees: int | None = None
    max_employees: int | None = None
    keywords: list[str] = []


ICP_PARSER_SYSTEM_PROMPT = """You are a B2B sales targeting expert. Parse natural language ICP (Ideal Customer Profile) descriptions into structured search filters for Apollo.io.

## Valid Seniority Values
Use ONLY these values: owner, founder, c_suite, partner, vp, head, director, manager, senior, entry

## Output Format
Respond with ONLY valid JSON matching this schema:
{
  "person_titles": ["CEO", "CTO"],
  "person_seniorities": ["c_suite", "founder"],
  "person_locations": ["United States"],
  "organization_industries": ["information technology & services"],
  "organization_locations": ["United States"],
  "min_employees": 10,
  "max_employees": 200,
  "keywords": ["SaaS", "cloud"]
}

## Rules
- Extract ALL relevant job titles mentioned or implied
- Map seniority terms to valid Apollo values (e.g. "executives" → "c_suite", "leaders" → "director,vp")
- Infer locations from country/city/region mentions
- Set organization_locations to match person_locations unless explicitly different
- Extract company size ranges when mentioned (e.g. "small companies" → 10-50, "mid-market" → 50-500)
- Extract industry keywords that aren't standard Apollo industries
- If something is ambiguous, include reasonable interpretations
- min_employees and max_employees should be null if not mentioned or implied"""


async def parse_icp(raw_text: str, llm: BaseChatModel) -> ICPFilters:
    """
    Parse a natural language ICP description into structured Apollo search filters.

    Args:
        raw_text: The plain-English ICP description from the user.
        llm: The LLM instance to use for parsing.

    Returns:
        ICPFilters with structured search parameters.
    """
    messages = [
        SystemMessage(content=ICP_PARSER_SYSTEM_PROMPT),
        HumanMessage(content=f"Parse this ICP into search filters:\n\n{raw_text}"),
    ]

    response = await llm.ainvoke(messages)
    content = response.content

    try:
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        parsed = json.loads(content.strip())
        return ICPFilters(**parsed)
    except (json.JSONDecodeError, ValueError, IndexError):
        logger.warning(
            "Failed to parse ICP filters from LLM response: %s", content[:200],
        )
        return ICPFilters()
