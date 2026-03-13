"""
Claude Pipe Router -- Smart routing between Agent Zero LLM and Claude Code CLI.

Decision logic:
  - Coding tasks (fix bug, edit file, refactor) -> Claude Code CLI
  - Conversation, analysis, planning -> Regular LLM via router
  - Hybrid (analyze then implement) -> LLM for analysis, Claude Code for implementation

Token savings: coding tasks use ~0 tokens from Agent Zero budget.
"""

import asyncio
import logging
import re
from typing import Optional

import httpx

from claude_code_tool import ClaudeCodeResult, run_coding_task, run_claude_code

log = logging.getLogger(__name__)

LLM_ROUTER_URL = "http://localhost:5100"

CODING_KEYWORDS = {
    "fix", "bug", "error", "patch", "refactor", "implement", "add feature",
    "write code", "edit file", "create file", "update", "modify",
    "replace", "delete function", "add endpoint", "write test",
    "migrate", "convert", "optimize", "debug", "deploy",
    "install", "configure", "setup", "script",
}

ANALYSIS_KEYWORDS = {
    "explain", "what is", "how does", "why", "compare", "analyze",
    "summarize", "describe", "list", "show me", "status",
    "plan", "suggest", "recommend", "review plan", "brainstorm",
}


def classify_task(message: str) -> str:
    """Classify a user message as 'code', 'analysis', or 'hybrid'."""
    lower = message.lower()
    has_code_patterns = bool(re.search(
        r'(\.(py|js|ts|go|rs|java|cpp|c|h|yaml|yml|json|toml|md)\b'
        r'|def\s+\w+|class\s+\w+|import\s+\w+|function\s+\w+'
        r'|```|fix\s+the|bug\s+in|error\s+in)',
        lower
    ))
    coding_score = sum(1 for kw in CODING_KEYWORDS if kw in lower)
    analysis_score = sum(1 for kw in ANALYSIS_KEYWORDS if kw in lower)
    if has_code_patterns:
        coding_score += 3
    if coding_score > analysis_score + 1:
        return "code"
    elif analysis_score > coding_score + 1:
        return "analysis"
    elif coding_score > 0 and analysis_score > 0:
        return "hybrid"
    elif coding_score > 0:
        return "code"
    return "analysis"


async def route_message(
    message: str, context: str = "", force_mode: Optional[str] = None,
) -> dict:
    """Route a message to the appropriate handler."""
    mode = force_mode or classify_task(message)
    log.info("Routing message as '%s': %s...", mode, message[:60])
    if mode == "code":
        return await _handle_coding(message, context)
    elif mode == "analysis":
        return await _handle_analysis(message, context)
    return await _handle_hybrid(message, context)


async def _handle_coding(task: str, context: str) -> dict:
    """Delegate coding task to Claude Code CLI."""
    result = await run_coding_task(task, context)
    response = result.output
    if result.files_changed:
        response += f"\n\nFiles changed: {', '.join(result.files_changed)}"
    if result.error:
        response = f"Error: {result.error}\n\n{response}"
    return {
        "response": response, "mode": "claude_code",
        "cost_usd": result.cost_usd, "files_changed": result.files_changed,
        "success": result.success,
    }


async def _handle_analysis(message: str, context: str) -> dict:
    """Handle analysis/conversation via regular LLM router."""
    prompt = message
    if context:
        prompt = f"{message}\n\nContext:\n{context}"
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{LLM_ROUTER_URL}/v1/chat/completions",
                json={
                    "messages": [{"role": "user", "content": prompt}],
                    "tier": "balanced", "temperature": 0.3, "max_tokens": 2000,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            response = data["choices"][0]["message"]["content"]
            return {
                "response": response, "mode": "llm_router",
                "cost_usd": data.get("usage", {}).get("cost_usd", 0),
                "files_changed": [], "success": True,
            }
    except Exception as e:
        log.error("LLM router error: %s", e)
        return {
            "response": f"LLM router error: {e}", "mode": "llm_router",
            "cost_usd": 0, "files_changed": [], "success": False,
        }


async def _handle_hybrid(message: str, context: str) -> dict:
    """Hybrid: LLM for planning, Claude Code for implementation."""
    plan_prompt = (
        f"Create a specific, step-by-step implementation plan for this task. "
        f"Include exact file paths and changes. Be concise.\n\nTask: {message}"
    )
    if context:
        plan_prompt += f"\n\nContext:\n{context}"
    plan_result = await _handle_analysis(plan_prompt, "")
    if not plan_result["success"]:
        return await _handle_coding(message, context)
    plan = plan_result["response"]
    code_prompt = f"Execute this implementation plan:\n\n{plan}\n\nOriginal task: {message}"
    code_result = await run_coding_task(code_prompt, context)
    response = f"**Plan:**\n{plan}\n\n**Execution:**\n{code_result.output}"
    if code_result.files_changed:
        response += f"\n\nFiles changed: {', '.join(code_result.files_changed)}"
    return {
        "response": response, "mode": "hybrid",
        "cost_usd": (plan_result.get("cost_usd", 0) or 0) + code_result.cost_usd,
        "files_changed": code_result.files_changed, "success": code_result.success,
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python claude_pipe_router.py 'your message here'")
        sys.exit(1)
    msg = " ".join(sys.argv[1:])
    classification = classify_task(msg)
    print(f"Classification: {classification}")
    result = asyncio.run(route_message(msg))
    print(f"Mode: {result['mode']}")
    print(f"Success: {result['success']}")
    print(f"Cost: ${result['cost_usd']:.4f}")
    if result['files_changed']:
        print(f"Files: {result['files_changed']}")
    print(f"\n{result['response']}")
