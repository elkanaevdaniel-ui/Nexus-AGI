"""Agent Zero tool — LinkedIn posting via the LinkedIn bot service."""

import json
import os
from typing import Any

import httpx

from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle

BOT_URL = os.environ.get("LINKEDIN_BOT_URL", "http://localhost:8083")
BOT_TIMEOUT = int(os.environ.get("LINKEDIN_BOT_TIMEOUT", "60"))

VALID_ACTIONS = ("generate", "approve", "schedule", "list")


class LinkedinPost(Tool):

    async def execute(self, **kwargs) -> Response:
        action: str = self.args.get("action", "")
        topic: str = self.args.get("topic", "")
        style: str = self.args.get("style", "")
        post_id: str = self.args.get("post_id", "")
        schedule_time: str = self.args.get("schedule_time", "")

        if not action or action not in VALID_ACTIONS:
            return Response(
                message=f"Error: 'action' must be one of {VALID_ACTIONS}.",
                break_loop=False,
            )

        PrintStyle(font_color="#0a66c2", bold=True).print(
            f"{self.agent.agent_name}: LinkedIn Bot — {action}"
        )

        try:
            if action == "generate":
                return await self._generate(topic, style)
            elif action == "approve":
                return await self._approve(post_id)
            elif action == "schedule":
                return await self._schedule(post_id, schedule_time)
            elif action == "list":
                return await self._list_posts()
        except httpx.ConnectError:
            return Response(
                message=(
                    f"LinkedIn bot is not reachable at {BOT_URL}. "
                    "Ensure the service is running."
                ),
                break_loop=False,
            )
        except httpx.HTTPStatusError as exc:
            return Response(
                message=f"LinkedIn bot error: {exc.response.status_code} — {exc.response.text}",
                break_loop=False,
            )

        return Response(message="Unknown error.", break_loop=False)

    async def _generate(self, topic: str, style: str) -> Response:
        if not topic:
            return Response(
                message="Error: 'topic' is required for the generate action.",
                break_loop=False,
            )

        payload: dict[str, Any] = {"topic": topic}
        if style:
            payload["style"] = style

        async with httpx.AsyncClient(timeout=BOT_TIMEOUT) as client:
            resp = await client.post(f"{BOT_URL}/posts/generate", json=payload)
            resp.raise_for_status()
            data = resp.json()

        draft = data.get("content", data.get("draft", ""))
        post_id = data.get("post_id", data.get("id", "N/A"))

        result = (
            f"**Draft Generated** (post_id: {post_id})\n\n"
            f"{draft}\n\n"
            "Use action='approve' with this post_id to publish, "
            "or action='schedule' to schedule it."
        )
        PrintStyle(font_color="#85C1E9").print(result)
        return Response(message=result, break_loop=False)

    async def _approve(self, post_id: str) -> Response:
        if not post_id:
            return Response(
                message="Error: 'post_id' is required for the approve action.",
                break_loop=False,
            )

        async with httpx.AsyncClient(timeout=BOT_TIMEOUT) as client:
            resp = await client.post(f"{BOT_URL}/posts/{post_id}/approve")
            resp.raise_for_status()
            data = resp.json()

        status = data.get("status", "approved")
        return Response(
            message=f"Post {post_id} has been {status}.",
            break_loop=False,
        )

    async def _schedule(self, post_id: str, schedule_time: str) -> Response:
        if not post_id:
            return Response(
                message="Error: 'post_id' is required for the schedule action.",
                break_loop=False,
            )
        if not schedule_time:
            return Response(
                message="Error: 'schedule_time' is required (ISO-8601 format).",
                break_loop=False,
            )

        async with httpx.AsyncClient(timeout=BOT_TIMEOUT) as client:
            resp = await client.post(
                f"{BOT_URL}/posts/{post_id}/schedule",
                json={"schedule_time": schedule_time},
            )
            resp.raise_for_status()
            data = resp.json()

        return Response(
            message=f"Post {post_id} scheduled for {data.get('scheduled_at', schedule_time)}.",
            break_loop=False,
        )

    async def _list_posts(self) -> Response:
        async with httpx.AsyncClient(timeout=BOT_TIMEOUT) as client:
            resp = await client.get(f"{BOT_URL}/posts")
            resp.raise_for_status()
            data = resp.json()

        posts = data.get("posts", data if isinstance(data, list) else [])
        if not posts:
            return Response(message="No posts found.", break_loop=False)

        lines: list[str] = ["**Recent LinkedIn Posts**\n"]
        for p in posts:
            pid = p.get("post_id", p.get("id", "?"))
            status = p.get("status", "unknown")
            snippet = p.get("content", p.get("draft", ""))[:80]
            lines.append(f"- [{pid}] ({status}) {snippet}...")

        result = "\n".join(lines)
        PrintStyle(font_color="#85C1E9").print(result)
        return Response(message=result, break_loop=False)
