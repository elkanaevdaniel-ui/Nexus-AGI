"""Apollo.io API client for lead discovery and enrichment."""

import json
import uuid
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import settings

APOLLO_BASE_URL = "https://api.apollo.io/api/v1"


class ApolloClient:
    """Async client for Apollo.io API."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or settings.apollo_api_key
        self._headers = {
            "x-api-key": self._api_key,
            "Content-Type": "application/json",
        }
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create a persistent httpx client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers=self._headers,
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=16),
    )
    async def _request(
        self,
        method: str,
        endpoint: str,
        payload: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an authenticated request to Apollo.io."""
        url = f"{APOLLO_BASE_URL}{endpoint}"

        # Apollo requires api_key in the POST body (not just the header)
        if method.upper() == "POST" and payload is not None:
            payload = {**payload, "api_key": self._api_key}
        elif method.upper() == "POST":
            payload = {"api_key": self._api_key}

        client = await self._get_client()
        response = await client.request(
            method=method,
            url=url,
            json=payload,
            params=params,
        )
        if response.status_code == 429:
            raise httpx.HTTPStatusError(
                "Rate limited by Apollo",
                request=response.request,
                response=response,
            )
        response.raise_for_status()
        return response.json()

    async def search_people(
        self,
        person_titles: list[str] | None = None,
        person_seniorities: list[str] | None = None,
        q_organization_domains: list[str] | None = None,
        organization_industry_tag_ids: list[str] | None = None,
        organization_num_employees_ranges: list[str] | None = None,
        person_locations: list[str] | None = None,
        q_keywords: str | None = None,
        page: int = 1,
        per_page: int = 25,
    ) -> dict[str, Any]:
        """
        Search for people on Apollo.io (free, no credits).

        Returns IDs + basic info. Use enrich_person for full data.
        """
        payload: dict[str, Any] = {
            "page": page,
            "per_page": min(per_page, 100),
        }
        if person_titles:
            payload["person_titles"] = person_titles
        if person_seniorities:
            payload["person_seniorities"] = person_seniorities
        if q_organization_domains:
            payload["q_organization_domains"] = "\n".join(q_organization_domains)
        if organization_industry_tag_ids:
            payload["organization_industry_tag_ids"] = organization_industry_tag_ids
        if organization_num_employees_ranges:
            payload["organization_num_employees_ranges"] = organization_num_employees_ranges
        if person_locations:
            payload["person_locations"] = person_locations
        if q_keywords:
            payload["q_keywords"] = q_keywords

        result = await self._request("POST", "/mixed_people/search", payload=payload)
        return result

    async def enrich_person(
        self,
        apollo_id: str | None = None,
        email: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        organization_name: str | None = None,
        domain: str | None = None,
        reveal_personal_emails: bool = False,
        reveal_phone_number: bool = False,
    ) -> dict[str, Any]:
        """
        Enrich a single person (costs 1 credit).

        Returns full contact data including email, phone, company details.
        """
        payload: dict[str, Any] = {}
        if apollo_id:
            payload["id"] = apollo_id
        if email:
            payload["email"] = email
        if first_name:
            payload["first_name"] = first_name
        if last_name:
            payload["last_name"] = last_name
        if organization_name:
            payload["organization_name"] = organization_name
        if domain:
            payload["domain"] = domain
        if reveal_personal_emails:
            payload["reveal_personal_emails"] = True
        if reveal_phone_number:
            payload["reveal_phone_number"] = True

        return await self._request("POST", "/people/match", payload=payload)

    async def bulk_enrich_people(
        self,
        details: list[dict[str, str]],
    ) -> dict[str, Any]:
        """
        Enrich up to 10 people at once.

        Each entry can have: id, email, first_name, last_name, organization_name, domain.
        """
        payload = {"details": details[:10]}
        return await self._request("POST", "/people/bulk_match", payload=payload)

    async def search_organizations(
        self,
        q_organization_name: str | None = None,
        organization_industry_tag_ids: list[str] | None = None,
        organization_num_employees_ranges: list[str] | None = None,
        organization_locations: list[str] | None = None,
        page: int = 1,
        per_page: int = 25,
    ) -> dict[str, Any]:
        """Search for organizations on Apollo.io."""
        payload: dict[str, Any] = {
            "page": page,
            "per_page": min(per_page, 100),
        }
        if q_organization_name:
            payload["q_organization_name"] = q_organization_name
        if organization_industry_tag_ids:
            payload["organization_industry_tag_ids"] = organization_industry_tag_ids
        if organization_num_employees_ranges:
            payload["organization_num_employees_ranges"] = organization_num_employees_ranges
        if organization_locations:
            payload["organization_locations"] = organization_locations

        return await self._request("POST", "/mixed_companies/search", payload=payload)

    async def get_usage(self) -> dict[str, Any]:
        """Get API usage stats (requires master key)."""
        return await self._request("GET", "/usage")


def parse_apollo_person(data: dict[str, Any]) -> dict[str, Any]:
    """Convert Apollo person response to our Lead format."""
    org = data.get("organization") or {}
    phone_numbers = data.get("phone_numbers") or []
    primary_phone = phone_numbers[0].get("number") if phone_numbers else None

    return {
        "id": str(uuid.uuid4()),
        "apollo_id": data.get("id"),
        "first_name": data.get("first_name", ""),
        "last_name": data.get("last_name", ""),
        "email": data.get("email"),
        "email_status": data.get("email_status"),
        "phone": primary_phone,
        "linkedin_url": data.get("linkedin_url"),
        "title": data.get("title"),
        "seniority": data.get("seniority"),
        "department": (data.get("departments") or [None])[0],
        "headline": data.get("headline"),
        "company_name": org.get("name"),
        "company_domain": org.get("website_url"),
        "company_industry": org.get("industry"),
        "company_size": org.get("estimated_num_employees"),
        "company_revenue": org.get("annual_revenue"),
        "company_location": _build_location(org),
        "source": "apollo",
        "raw_data": json.dumps(data),
    }


def _build_location(org: dict[str, Any]) -> str | None:
    """Build a location string from Apollo org data."""
    parts = [
        org.get("city"),
        org.get("state"),
        org.get("country"),
    ]
    filtered = [p for p in parts if p]
    return ", ".join(filtered) if filtered else None
