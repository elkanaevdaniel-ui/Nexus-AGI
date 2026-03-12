"""Agent Zero tool — Lead generation via the lead-gen service."""

import json
import os
from typing import Any

import httpx

from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle

SERVICE_URL = os.environ.get("LEAD_GEN_URL", "http://localhost:8082")
SERVICE_TIMEOUT = int(os.environ.get("LEAD_GEN_TIMEOUT", "60"))

VALID_ACTIONS = ("search", "score", "campaign", "export")


class LeadGen(Tool):

    async def execute(self, **kwargs) -> Response:
        action: str = self.args.get("action", "")
        query: str = self.args.get("query", "")
        campaign_id: str = self.args.get("campaign_id", "")
        campaign_name: str = self.args.get("campaign_name", "")
        lead_id: str = self.args.get("lead_id", "")
        limit: str = self.args.get("limit", "20")

        if not action or action not in VALID_ACTIONS:
            return Response(
                message=f"Error: 'action' must be one of {VALID_ACTIONS}.",
                break_loop=False,
            )

        PrintStyle(font_color="#e67e22", bold=True).print(
            f"{self.agent.agent_name}: Lead Gen — {action}"
        )

        try:
            if action == "search":
                return await self._search(query, limit)
            elif action == "score":
                return await self._score(campaign_id)
            elif action == "campaign":
                return await self._campaign(campaign_id, campaign_name, query)
            elif action == "export":
                return await self._export(campaign_id)
        except httpx.ConnectError:
            return Response(
                message=(
                    f"Lead-gen service is not reachable at {SERVICE_URL}. "
                    "Ensure the service is running."
                ),
                break_loop=False,
            )
        except httpx.HTTPStatusError as exc:
            return Response(
                message=f"Lead-gen service error: {exc.response.status_code} — {exc.response.text}",
                break_loop=False,
            )

        return Response(message="Unknown error.", break_loop=False)

    async def _search(self, query: str, limit: str) -> Response:
        if not query:
            return Response(
                message="Error: 'query' is required for the search action.",
                break_loop=False,
            )

        params: dict[str, Any] = {"q": query, "limit": int(limit)}
        async with httpx.AsyncClient(timeout=SERVICE_TIMEOUT) as client:
            resp = await client.get(f"{SERVICE_URL}/leads/search", params=params)
            resp.raise_for_status()
            data = resp.json()

        leads = data.get("leads", data if isinstance(data, list) else [])
        if not leads:
            return Response(message="No leads found matching the query.", break_loop=False)

        lines: list[str] = [f"**Lead Search Results** ({len(leads)} found)\n"]
        for lead in leads:
            lid = lead.get("lead_id", lead.get("id", "?"))
            name = lead.get("name", lead.get("company", "Unknown"))
            email = lead.get("email", "N/A")
            score = lead.get("score", "unscored")
            lines.append(f"- [{lid}] {name} — {email} (score: {score})")

        result = "\n".join(lines)
        PrintStyle(font_color="#85C1E9").print(result)
        return Response(message=result, break_loop=False)

    async def _score(self, campaign_id: str) -> Response:
        if not campaign_id:
            return Response(
                message="Error: 'campaign_id' is required for the score action.",
                break_loop=False,
            )

        async with httpx.AsyncClient(timeout=SERVICE_TIMEOUT) as client:
            resp = await client.post(
                f"{SERVICE_URL}/campaigns/{campaign_id}/score",
            )
            resp.raise_for_status()
            data = resp.json()

        scored = data.get("scored_count", data.get("total", "N/A"))
        avg_score = data.get("average_score", "N/A")

        result = (
            f"**Scoring Complete — Campaign {campaign_id}**\n\n"
            f"Leads scored: {scored}\n"
            f"Average score: {avg_score}"
        )
        PrintStyle(font_color="#85C1E9").print(result)
        return Response(message=result, break_loop=False)

    async def _campaign(
        self, campaign_id: str, campaign_name: str, query: str,
    ) -> Response:
        async with httpx.AsyncClient(timeout=SERVICE_TIMEOUT) as client:
            if campaign_id:
                # Get existing campaign
                resp = await client.get(
                    f"{SERVICE_URL}/campaigns/{campaign_id}",
                )
                resp.raise_for_status()
                data = resp.json()
                name = data.get("name", campaign_id)
                status = data.get("status", "unknown")
                lead_count = data.get("lead_count", "N/A")
                result = (
                    f"**Campaign: {name}** (id: {campaign_id})\n\n"
                    f"Status: {status}\n"
                    f"Leads: {lead_count}"
                )
            else:
                # Create new campaign
                if not campaign_name:
                    return Response(
                        message="Error: 'campaign_name' is required to create a campaign.",
                        break_loop=False,
                    )
                payload: dict[str, Any] = {"name": campaign_name}
                if query:
                    payload["query"] = query
                resp = await client.post(
                    f"{SERVICE_URL}/campaigns",
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                cid = data.get("campaign_id", data.get("id", "N/A"))
                result = f"Campaign '{campaign_name}' created with id: {cid}."

        PrintStyle(font_color="#85C1E9").print(result)
        return Response(message=result, break_loop=False)

    async def _export(self, campaign_id: str) -> Response:
        if not campaign_id:
            return Response(
                message="Error: 'campaign_id' is required for the export action.",
                break_loop=False,
            )

        async with httpx.AsyncClient(timeout=SERVICE_TIMEOUT) as client:
            resp = await client.get(
                f"{SERVICE_URL}/campaigns/{campaign_id}/export",
            )
            resp.raise_for_status()

            content_type = resp.headers.get("content-type", "")
            if "csv" in content_type or "text" in content_type:
                csv_data = resp.text
                lines = csv_data.strip().split("\n")
                preview = "\n".join(lines[:11])  # header + 10 rows
                total = len(lines) - 1
                result = (
                    f"**Exported {total} leads from campaign {campaign_id}**\n\n"
                    f"```csv\n{preview}\n```"
                )
            else:
                data = resp.json()
                url = data.get("download_url", data.get("url", ""))
                count = data.get("count", "N/A")
                result = (
                    f"Export ready: {count} leads from campaign {campaign_id}.\n"
                    f"Download: {url}"
                )

        PrintStyle(font_color="#85C1E9").print(result)
        return Response(message=result, break_loop=False)
