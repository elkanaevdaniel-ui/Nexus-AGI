"""
Agent Zero -> Claude Code CLI Pipe

This tool allows Agent Zero to delegate coding tasks to Claude Code CLI,
saving tokens on the primary LLM while getting high-quality code changes.

Flow:
  1. Agent Zero receives a coding request via Telegram/Web UI
  2. Instead of using expensive LLM tokens for code generation,
     it pipes the task to Claude Code CLI
  3. Claude Code CLI executes the task (reading files, editing, running tests)
  4. Results are streamed back to Agent Zero for presentation

Benefits:
  - Saves 80-90% of LLM tokens on coding tasks
  - Claude Code has full file system access and tool use
  - Maintains the "smart sub pro max plan" coding quality
  - Agent Zero handles orchestration, Claude Code handles implementation

Setup:
  - Claude Code CLI must be installed: npm install -g @anthropic-ai/claude-code
  - ANTHROPIC_API_KEY must be set in environment
  - This module runs as a subprocess, not an HTTP service
"""

import asyncio
import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# -- Configuration ----------------------------------------------------------------
CLAUDE_CODE_BIN = os.getenv("CLAUDE_CODE_BIN", "claude")
PROJECT_ROOT = os.getenv("NEXUS_PROJECT_ROOT", os.path.expanduser("~/ai-projects/workdir"))
MAX_TIMEOUT = int(os.getenv("CLAUDE_CODE_TIMEOUT", "300"))  # 5 min default
MAX_TURNS = int(os.getenv("CLAUDE_CODE_MAX_TURNS", "20"))


@dataclass
class ClaudeCodeResult:
    """Result from a Claude Code CLI execution."""
    success: bool
    output: str
    cost_usd: float = 0.0
    files_changed: list[str] = field(default_factory=list)
    error: Optional[str] = None
    session_id: Optional[str] = None


async def run_claude_code(
    prompt: str,
    working_dir: Optional[str] = None,
    allowed_tools: Optional[list[str]] = None,
    max_turns: int = MAX_TURNS,
    timeout: int = MAX_TIMEOUT,
) -> ClaudeCodeResult:
    """
    Run Claude Code CLI with a prompt and return structured results.
    """
    cwd = working_dir or PROJECT_ROOT

    cmd = [
        CLAUDE_CODE_BIN,
        "--print",
        "--output-format", "json",
        "--max-turns", str(max_turns),
    ]

    if allowed_tools:
        cmd.extend(["--allowedTools", ",".join(allowed_tools)])

    log.info("Running Claude Code: cwd=%s, prompt=%s...", cwd, prompt[:80])

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env={**os.environ, "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"},
        )

        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=prompt.encode()),
            timeout=timeout,
        )

        stdout_text = stdout.decode().strip()
        stderr_text = stderr.decode().strip()

        if proc.returncode != 0:
            log.error("Claude Code failed (rc=%d): %s", proc.returncode, stderr_text)
            return ClaudeCodeResult(
                success=False,
                output=stderr_text or stdout_text,
                error=f"Exit code {proc.returncode}",
            )

        result = _parse_claude_output(stdout_text)
        result.success = True
        return result

    except asyncio.TimeoutError:
        log.error("Claude Code timed out after %ds", timeout)
        if proc:
            proc.kill()
        return ClaudeCodeResult(success=False, output="", error=f"Timed out after {timeout}s")
    except FileNotFoundError:
        return ClaudeCodeResult(
            success=False, output="",
            error=f"Claude Code CLI not found at '{CLAUDE_CODE_BIN}'. Install: npm install -g @anthropic-ai/claude-code",
        )
    except Exception as e:
        log.exception("Claude Code execution error")
        return ClaudeCodeResult(success=False, output="", error=str(e))


def _parse_claude_output(raw: str) -> ClaudeCodeResult:
    """Parse Claude Code JSON output into a structured result."""
    try:
        lines = raw.strip().split("\n")
        messages = []
        cost = 0.0
        session_id = None
        files_changed = set()

        for line in lines:
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg_type = obj.get("type", "")

            if msg_type == "result":
                cost = obj.get("cost_usd", 0.0) or obj.get("total_cost", 0.0) or 0.0
                session_id = obj.get("session_id")
                result_text = obj.get("result", "")
                if result_text:
                    messages.append(result_text)

            elif msg_type == "assistant":
                content = obj.get("message", {}).get("content", [])
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        messages.append(block["text"])
                    elif isinstance(block, dict) and block.get("type") == "tool_use":
                        tool_name = block.get("name", "")
                        tool_input = block.get("input", {})
                        if tool_name in ("Edit", "Write") and "file_path" in tool_input:
                            files_changed.add(tool_input["file_path"])

        output = "\n".join(messages) if messages else raw
        return ClaudeCodeResult(
            success=True, output=output, cost_usd=cost,
            files_changed=sorted(files_changed), session_id=session_id,
        )
    except Exception as e:
        log.warning("Failed to parse Claude output: %s", e)
        return ClaudeCodeResult(success=True, output=raw)


async def run_coding_task(task: str, context: str = "") -> ClaudeCodeResult:
    """High-level wrapper for coding tasks from Agent Zero."""
    prompt_parts = [
        "You are working on the Nexus-AGI project.",
        "Read CLAUDE.md first for project rules and conventions.",
        "",
        f"Task: {task}",
    ]
    if context:
        prompt_parts.extend(["", "Additional context:", context])
    prompt_parts.extend([
        "", "Requirements:",
        "- Follow all rules in CLAUDE.md (async-first, httpx, type hints, etc.)",
        "- Verify your changes work (syntax check, import check)",
        "- Keep changes minimal and focused",
        "- Report what files you changed and what you did",
    ])
    prompt = "\n".join(prompt_parts)
    return await run_claude_code(
        prompt=prompt,
        allowed_tools=["Read", "Edit", "Write", "Bash", "Glob", "Grep"],
    )


class ClaudeCodeTool:
    """Agent Zero tool class for Claude Code CLI integration."""
    name = "claude_code"
    description = (
        "Delegate coding tasks to Claude Code CLI for high-quality code changes. "
        "Use for: fixing bugs, refactoring, adding features, writing tests, "
        "reviewing code, or any task involving reading/editing source files."
    )

    async def execute(self, task: str, context: str = "", **kwargs) -> dict:
        result = await run_coding_task(task, context)
        return {
            "success": result.success, "output": result.output,
            "files_changed": result.files_changed,
            "cost_usd": result.cost_usd, "error": result.error,
        }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python claude_code_tool.py 'your coding task here'")
        sys.exit(1)
    task = " ".join(sys.argv[1:])
    result = asyncio.run(run_coding_task(task))
    print(f"\n{'='*60}")
    print(f"Success: {result.success}")
    print(f"Cost: ${result.cost_usd:.4f}")
    print(f"Files changed: {result.files_changed}")
    if result.error:
        print(f"Error: {result.error}")
    print(f"{'='*60}")
    print(result.output)
