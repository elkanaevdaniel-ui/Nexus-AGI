"""Nexus service health check API — checks all Nexus-AGI services."""

import os
import asyncio

import httpx

from python.helpers.api import ApiHandler, Input, Output, Request


# Service definitions with their health endpoints
NEXUS_SERVICES = {
    "claude-adapter": {
        "name": "Claude Code Adapter",
        "url": os.environ.get("CLAUDE_ADAPTER_URL", "http://localhost:8090"),
        "health_path": "/health",
    },
    "linkedin-bot": {
        "name": "LinkedIn Bot",
        "url": os.environ.get("LINKEDIN_BOT_URL", "http://localhost:8083"),
        "health_path": "/health",
    },
    "trading": {
        "name": "Trading Agent",
        "url": os.environ.get("TRADING_SERVICE_URL", "http://localhost:8000"),
        "health_path": "/health",
    },
    "lead-gen": {
        "name": "Lead Gen",
        "url": os.environ.get("LEAD_GEN_URL", "http://localhost:8082"),
        "health_path": "/health",
    },
    "llm-router": {
        "name": "LLM Router",
        "url": os.environ.get("LLM_ROUTER_URL", "http://localhost:8091"),
        "health_path": "/health",
    },
    "cost-tracker": {
        "name": "Cost Tracker",
        "url": os.environ.get("COST_TRACKER_URL", "http://localhost:8092"),
        "health_path": "/health",
    },
}


class NexusHealth(ApiHandler):

    @classmethod
    def get_methods(cls) -> list[str]:
        return ["GET", "POST"]

    @classmethod
    def requires_auth(cls) -> bool:
        return True

    async def process(self, input: Input, request: Request) -> Output:
        action = input.get("action", "all")
        service_id = input.get("service_id", "")

        if action == "check" and service_id:
            # Check a single service
            if service_id not in NEXUS_SERVICES:
                return {"ok": False, "error": f"Unknown service: {service_id}"}
            result = await self._check_service(service_id)
            return {"ok": True, "data": result}

        # Check all services
        results = await self._check_all()
        return {"ok": True, "data": results}

    async def _check_all(self) -> list[dict]:
        """Check all services concurrently."""
        tasks = [self._check_service(sid) for sid in NEXUS_SERVICES]
        return await asyncio.gather(*tasks)

    async def _check_service(self, service_id: str) -> dict:
        """Check a single service health."""
        svc = NEXUS_SERVICES[service_id]
        url = f"{svc['url']}{svc['health_path']}"

        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(url)
                return {
                    "id": service_id,
                    "name": svc["name"],
                    "status": "online" if resp.status_code == 200 else "degraded",
                    "code": resp.status_code,
                    "url": svc["url"],
                }
        except httpx.ConnectError:
            return {
                "id": service_id,
                "name": svc["name"],
                "status": "offline",
                "code": None,
                "url": svc["url"],
            }
        except Exception as exc:
            return {
                "id": service_id,
                "name": svc["name"],
                "status": "error",
                "code": None,
                "url": svc["url"],
                "error": str(exc),
            }
