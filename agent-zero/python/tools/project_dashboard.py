"""Agent Zero tool — Nexus-AGI project dashboard and service management."""

import asyncio
import os

import httpx

from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle

SERVICES: dict[str, dict[str, str]] = {
    "trading": {
        "url": os.environ.get("TRADING_SERVICE_URL", "http://localhost:8000"),
        "health": "/health",
    },
    "linkedin": {
        "url": os.environ.get("LINKEDIN_BOT_URL", "http://localhost:8083"),
        "health": "/health",
    },
    "lead-gen": {
        "url": os.environ.get("LEAD_GEN_URL", "http://localhost:8082"),
        "health": "/health",
    },
    "claude-adapter": {
        "url": os.environ.get("CLAUDE_ADAPTER_URL", "http://localhost:8090"),
        "health": "/health",
    },
}

MANAGER_URL = os.environ.get("SERVICE_MANAGER_URL", "http://localhost:9000")
TIMEOUT = int(os.environ.get("DASHBOARD_TIMEOUT", "10"))

VALID_ACTIONS = ("status", "start", "stop", "restart", "logs")


class ProjectDashboard(Tool):

    async def execute(self, **kwargs) -> Response:
        action: str = self.args.get("action", "")
        service: str = self.args.get("service", "")

        if not action or action not in VALID_ACTIONS:
            return Response(
                message=f"Error: 'action' must be one of {VALID_ACTIONS}.",
                break_loop=False,
            )

        PrintStyle(font_color="#8e44ad", bold=True).print(
            f"{self.agent.agent_name}: Dashboard — {action}"
        )

        if action == "status":
            return await self._status()
        elif action in ("start", "stop", "restart"):
            return await self._manage(action, service)
        elif action == "logs":
            return await self._logs(service)

        return Response(message="Unknown error.", break_loop=False)

    async def _check_service(self, name: str, info: dict[str, str]) -> dict:
        url = info["url"] + info["health"]
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                return {
                    "name": name,
                    "url": info["url"],
                    "status": "UP",
                    "version": data.get("version", ""),
                    "uptime": data.get("uptime", ""),
                }
        except (httpx.ConnectError, httpx.HTTPStatusError, httpx.ReadTimeout, Exception):
            return {
                "name": name,
                "url": info["url"],
                "status": "DOWN",
                "version": "",
                "uptime": "",
            }

    async def _status(self) -> Response:
        tasks = [
            self._check_service(name, info)
            for name, info in SERVICES.items()
        ]
        results = await asyncio.gather(*tasks)

        up_count = sum(1 for r in results if r["status"] == "UP")
        total = len(results)

        lines: list[str] = [
            "**Nexus-AGI Dashboard**\n",
            f"Services: {up_count}/{total} running\n",
            f"{'Service':<18} {'Status':<8} {'URL':<30} {'Version':<10}",
            "-" * 70,
        ]
        for r in results:
            indicator = "OK" if r["status"] == "UP" else "XX"
            version = r["version"] or "-"
            lines.append(
                f"{r['name']:<18} [{indicator}]    {r['url']:<30} {version:<10}"
            )

        result = "\n".join(lines)
        PrintStyle(font_color="#85C1E9").print(result)
        return Response(message=result, break_loop=False)

    async def _manage(self, action: str, service: str) -> Response:
        if not service:
            return Response(
                message=(
                    f"Error: 'service' is required for {action}. "
                    f"Available: {', '.join(SERVICES.keys())}"
                ),
                break_loop=False,
            )

        if service not in SERVICES:
            return Response(
                message=f"Error: unknown service '{service}'. Available: {', '.join(SERVICES.keys())}",
                break_loop=False,
            )

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{MANAGER_URL}/services/{service}/{action}",
                )
                resp.raise_for_status()
                data = resp.json()

            status = data.get("status", action + "ed")
            return Response(
                message=f"Service '{service}' — {status}.",
                break_loop=False,
            )
        except httpx.ConnectError:
            return Response(
                message=(
                    f"Service manager is not reachable at {MANAGER_URL}. "
                    "Cannot manage services remotely. "
                    "Try starting the service manually."
                ),
                break_loop=False,
            )
        except httpx.HTTPStatusError as exc:
            return Response(
                message=f"Service manager error: {exc.response.status_code} — {exc.response.text}",
                break_loop=False,
            )

    async def _logs(self, service: str) -> Response:
        if not service:
            return Response(
                message=(
                    "Error: 'service' is required for logs. "
                    f"Available: {', '.join(SERVICES.keys())}"
                ),
                break_loop=False,
            )

        if service not in SERVICES:
            return Response(
                message=f"Error: unknown service '{service}'. Available: {', '.join(SERVICES.keys())}",
                break_loop=False,
            )

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{MANAGER_URL}/services/{service}/logs",
                    params={"lines": 50},
                )
                resp.raise_for_status()
                data = resp.json()

            logs = data.get("logs", data.get("output", ""))
            return Response(
                message=f"**Logs — {service}**\n\n```\n{logs}\n```",
                break_loop=False,
            )
        except httpx.ConnectError:
            return Response(
                message=(
                    f"Service manager is not reachable at {MANAGER_URL}. "
                    "Cannot retrieve logs remotely."
                ),
                break_loop=False,
            )
        except httpx.HTTPStatusError as exc:
            return Response(
                message=f"Service manager error: {exc.response.status_code} — {exc.response.text}",
                break_loop=False,
            )
