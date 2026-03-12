"""Agent Zero tool — routes coding tasks to Claude Code Adapter Service.

Enhanced with task classification, dynamic timeouts, workflow chaining,
and session cost limits from the polymarket-agent pipeline.
"""

import json
import os

import httpx

from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle

ADAPTER_URL = os.environ.get("CLAUDE_ADAPTER_URL", "http://localhost:8090")
ADAPTER_API_KEY = os.environ.get("CLAUDE_ADAPTER_API_KEY", "")
ADAPTER_TIMEOUT = int(os.environ.get("CLAUDE_ADAPTER_TIMEOUT", "300"))

# Session call counter (resets per Agent Zero session)
_session_call_count = 0
MAX_CALLS_PER_SESSION = int(os.environ.get("CLAUDE_MAX_CALLS_PER_SESSION", "10"))

# Task classification for dynamic timeouts and risk levels
TASK_TYPES = {
    "read": {
        "keywords": ["read", "show", "list", "check", "status", "cat", "grep", "find"],
        "timeout": 300,
        "risk": "low",
    },
    "test": {
        "keywords": ["test", "pytest", "verify", "validate", "lint", "check syntax"],
        "timeout": 300,
        "risk": "low",
    },
    "analysis": {
        "keywords": ["analyze", "research", "evaluate", "compare", "review", "assess",
                      "probability", "market", "estimate", "forecast", "news"],
        "timeout": 900,
        "risk": "low",
    },
    "coding": {
        "keywords": ["fix", "add", "implement", "refactor", "create", "write", "update",
                      "modify", "change", "build", "remove", "delete", "migrate"],
        "timeout": 600,
        "risk": "medium",
    },
    "trade": {
        "keywords": ["trade", "approve", "execute", "buy", "sell", "order", "position",
                      "live", "deploy", "push"],
        "timeout": 300,
        "risk": "high",
    },
}

# Workflow chain templates
WORKFLOW_CHAINS = {
    "full_trading_pipeline": {
        "description": "Scan → Analyze → Risk Check → Present",
        "steps": [
            {
                "name": "scan_markets",
                "prompt": (
                    "Run the market scanner. Execute a market scan and return a list of "
                    "markets with good volume and liquidity. Format as a table."
                ),
            },
            {
                "name": "analyze_opportunities",
                "prompt": (
                    "Analyze the top markets from scan results for trading opportunities. "
                    "Estimate true probability, calculate edge vs market price, "
                    "determine Kelly sizing. Search the web for recent news."
                ),
            },
            {
                "name": "risk_check",
                "prompt": (
                    "Check current portfolio state and verify proposed trades pass all "
                    "risk checks: daily loss limit, drawdown, position concentration."
                ),
            },
        ],
    },
    "code_and_verify": {
        "description": "Code → Test → Security Scan",
        "steps": [
            {"name": "implement", "prompt": "{coding_mission}"},
            {"name": "test", "prompt": "Run pytest -x -v. Fix any failures. Report results."},
            {
                "name": "security_scan",
                "prompt": (
                    "Security scan on recently changed files: git diff --name-only HEAD~1 HEAD. "
                    "Check for hardcoded secrets, SQL injection, command injection, XSS."
                ),
            },
        ],
    },
}


def _classify_task(prompt: str) -> tuple[str, int, str]:
    """Classify task → (type, timeout, risk)."""
    prompt_lower = prompt.lower()
    scores = {}
    for task_type, config in TASK_TYPES.items():
        scores[task_type] = sum(1 for kw in config["keywords"] if kw in prompt_lower)

    best = max(scores, key=scores.get) if max(scores.values()) > 0 else "coding"
    cfg = TASK_TYPES[best]
    return best, cfg["timeout"], cfg["risk"]


class ClaudeCode(Tool):
    """Routes coding tasks to Claude Code Adapter with task classification and workflow chains."""

    async def execute(self, **kwargs) -> Response:
        global _session_call_count

        prompt = self.args.get("prompt", "")
        working_dir = self.args.get("working_dir", None)
        workflow = self.args.get("workflow", "")

        # Workflow chaining
        if workflow and workflow in WORKFLOW_CHAINS:
            return await self._run_workflow(workflow, working_dir)

        if not prompt:
            return Response(message="Error: 'prompt' argument is required.", break_loop=False)

        # Session limit check
        _session_call_count += 1
        if _session_call_count > MAX_CALLS_PER_SESSION:
            return Response(
                message=f"Session limit reached ({MAX_CALLS_PER_SESSION} calls). "
                        f"Ask user to approve more calls (costs money).",
                break_loop=False,
            )

        # Classify task
        task_type, timeout, risk = _classify_task(prompt)
        timeout = min(timeout, ADAPTER_TIMEOUT)

        risk_colors = {"low": "#27AE60", "medium": "#F39C12", "high": "#E74C3C"}
        PrintStyle(font_color="#6366f1", bold=True).print(
            f"{self.agent.agent_name}: Claude Code — {task_type.upper()} task"
        )
        PrintStyle(font_color=risk_colors.get(risk, "#85C1E9")).print(
            f"Risk: {risk} | Timeout: {timeout}s | Call #{_session_call_count}/{MAX_CALLS_PER_SESSION}"
        )

        return await self._execute_task(prompt, working_dir, timeout)

    async def _execute_task(self, prompt: str, working_dir: str | None, timeout: int) -> Response:
        """Submit task to adapter and stream results."""
        headers = {}
        if ADAPTER_API_KEY:
            headers["x-api-key"] = ADAPTER_API_KEY

        # Submit task
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{ADAPTER_URL}/task",
                    json={"prompt": prompt, "working_dir": working_dir},
                    headers=headers,
                )
                resp.raise_for_status()
                task_data = resp.json()
                task_id = task_data["task_id"]
        except httpx.ConnectError:
            return Response(
                message=f"Claude Code Adapter unreachable at {ADAPTER_URL}. Is it running?",
                break_loop=False,
            )
        except httpx.HTTPStatusError as exc:
            return Response(
                message=f"Adapter error: {exc.response.status_code} — {exc.response.text}",
                break_loop=False,
            )

        # Stream results via SSE
        output_parts: list[str] = []
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=10)) as client:
                async with client.stream(
                    "GET", f"{ADAPTER_URL}/task/{task_id}/stream", headers=headers,
                ) as stream:
                    async for line in stream.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        try:
                            data = json.loads(line[6:])
                        except json.JSONDecodeError:
                            continue

                        if "text" in data:
                            chunk = data["text"]
                            output_parts.append(chunk)
                            PrintStyle(font_color="#85C1E9").stream(chunk)
                            self.add_progress(chunk)
                            if self.log:
                                self.log.update(content="".join(output_parts))

                        if "action" in data:
                            PrintStyle(font_color="#f59e0b", bold=True).print(
                                f"Approval requested: {data['action']}"
                            )
                            await client.post(
                                f"{ADAPTER_URL}/task/{task_id}/approve",
                                headers=headers,
                            )

        except httpx.ReadTimeout:
            output_parts.append("\n[timeout] Claude Code task timed out.")

        result = "".join(output_parts)
        if not result.strip():
            result = "Claude Code returned no output."

        return Response(message=result, break_loop=False)

    async def _run_workflow(self, workflow_name: str, working_dir: str | None) -> Response:
        """Execute a multi-step workflow chain."""
        global _session_call_count

        chain = WORKFLOW_CHAINS[workflow_name]
        PrintStyle(font_color="#8E44AD", bold=True).print(
            f"Workflow: {chain['description']}"
        )

        results: list[str] = []
        for i, step in enumerate(chain["steps"]):
            _session_call_count += 1
            if _session_call_count > MAX_CALLS_PER_SESSION:
                results.append(f"### Step {i+1}: {step['name']} — SKIPPED (session limit)")
                break

            PrintStyle(font_color="#3498DB", bold=True).print(
                f"  Step {i+1}/{len(chain['steps'])}: {step['name']}"
            )

            prompt = step["prompt"]
            _, timeout, _ = _classify_task(prompt)
            step_result = await self._execute_task(prompt, working_dir, timeout)
            results.append(f"### Step {i+1}: {step['name']}\n{step_result.message[:2000]}")

        full = (
            f"## Workflow: {workflow_name}\n"
            f"**Chain**: {chain['description']}\n"
            f"**Calls**: {_session_call_count}/{MAX_CALLS_PER_SESSION}\n\n"
            + "\n\n".join(results)
        )
        return Response(message=full, break_loop=False)
