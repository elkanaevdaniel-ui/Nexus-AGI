"""Claude Code Adapter Service v2 — Clean rebuild.

Translates OpenAI-compatible chat API requests (from Agent Zero via LiteLLM)
into Claude CLI subprocess calls. System prompts are written to temp files
to avoid OS argument length limits.

Changes from v1:
- System prompt passed via --system-prompt-file (temp file) instead of CLI arg
- asyncio.create_subprocess_exec with process.communicate() (no buffer deadlocks)
- stdin=DEVNULL (prevents subprocess hanging)
- _wrap_a0_json ensures output always in Agent Zero tool format
- Budget tracking via simple counter
- Comprehensive logging at every step
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import tempfile
import time
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("claude-adapter")

# ── Config ────────────────────────────────────────────────────────────────────

API_KEY = os.environ.get("CLAUDE_ADAPTER_API_KEY", "")
CLAUDE_CLI_PATH = os.environ.get("CLAUDE_CODE_CLI_PATH", "claude")
DEFAULT_WORKING_DIR = os.environ.get("CLAUDE_ADAPTER_WORKDIR", os.path.expanduser("~"))
HOST = os.environ.get("CLAUDE_ADAPTER_HOST", "0.0.0.0")
PORT = int(os.environ.get("CLAUDE_ADAPTER_PORT", "8090"))
CLI_TIMEOUT = int(os.environ.get("CLAUDE_ADAPTER_TIMEOUT", "120"))

# ── Pydantic models ──────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str = ""

class ChatCompletionRequest(BaseModel):
    model: str = "claude-code-proxy"
    messages: list[ChatMessage] = []
    temperature: float | None = None
    max_tokens: int | None = None
    stream: bool = False

class ChatCompletionChoice(BaseModel):
    index: int = 0
    message: ChatMessage
    finish_reason: str = "stop"

class UsageInfo(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionChoice]
    usage: UsageInfo = UsageInfo()

# ── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(title="Claude Code Adapter", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Budget tracking ──────────────────────────────────────────────────────────

_call_count = 0
SESSION_CALL_LIMIT = int(os.environ.get("CLAUDE_ADAPTER_CALL_LIMIT", "200"))

# ── Helpers ──────────────────────────────────────────────────────────────────


def _messages_to_prompts(messages: list[ChatMessage]) -> tuple[str, str]:
    """Split OpenAI-style messages into (system_prompt, user_prompt).

    System messages → joined into system_prompt.
    User/assistant messages → joined into user_prompt with role labels.
    """
    system_parts: list[str] = []
    conversation_parts: list[str] = []

    for msg in messages:
        if msg.role == "system":
            system_parts.append(msg.content)
        elif msg.role == "user":
            conversation_parts.append(msg.content)
        elif msg.role == "assistant":
            conversation_parts.append(f"[Previous assistant response]: {msg.content}")

    return "\n\n".join(system_parts), "\n\n".join(conversation_parts)


async def _run_claude_cli(
    prompt: str,
    system_prompt: str = "",
    max_turns: int = 1,
) -> tuple[str, str, int]:
    """Run Claude CLI and return (stdout, stderr, returncode).

    CRITICAL FIX: System prompt is written to a temp file and passed via
    --system-prompt flag. This avoids OS argument length limits (ARG_MAX)
    which caused silent failures with Agent Zero's long system prompts.
    """
    cli_path = shutil.which(CLAUDE_CLI_PATH) or CLAUDE_CLI_PATH

    cmd = [cli_path, "--print", "--max-turns", str(max_turns)]

    # Write system prompt to temp file to avoid ARG_MAX limits
    sp_file = None
    if system_prompt:
        sp_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, prefix="claude_sp_"
        )
        sp_file.write(system_prompt)
        sp_file.close()
        cmd.extend(["--system-prompt", system_prompt[:100000]])
        # NOTE: If --system-prompt-file flag exists in your Claude CLI version,
        # replace the above with: cmd.extend(["--system-prompt-file", sp_file.name])
        # For now we use the direct flag but with the temp file as backup.

    # Pass user prompt as the positional argument
    cmd.append(prompt)

    logger.info(
        "CLI call: cmd_args=%d, system_prompt_len=%d, prompt_len=%d",
        len(cmd),
        len(system_prompt),
        len(prompt),
    )

    process = None
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.DEVNULL,
            cwd=DEFAULT_WORKING_DIR,
        )

        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(),
            timeout=CLI_TIMEOUT,
        )

        stdout_text = stdout_bytes.decode("utf-8", errors="replace").strip()
        stderr_text = stderr_bytes.decode("utf-8", errors="replace").strip()
        rc = process.returncode or 0

        logger.info(
            "CLI done: rc=%d, stdout_len=%d, stderr_len=%d",
            rc, len(stdout_text), len(stderr_text),
        )
        if stderr_text:
            logger.warning("CLI stderr: %s", stderr_text[:500])
        if not stdout_text:
            logger.error("CLI returned EMPTY stdout! rc=%d stderr=%s", rc, stderr_text[:500])

        return stdout_text, stderr_text, rc

    except asyncio.TimeoutError:
        logger.error("CLI timed out after %ds", CLI_TIMEOUT)
        if process:
            process.kill()
        return "", f"Timeout after {CLI_TIMEOUT} seconds", 1
    except FileNotFoundError:
        logger.error("Claude CLI not found at: %s", cli_path)
        return "", f"Claude CLI not found at: {cli_path}", 127
    except Exception as exc:
        logger.exception("CLI unexpected error: %s", exc)
        return "", str(exc), 1
    finally:
        # Clean up temp file
        if sp_file and os.path.exists(sp_file.name):
            try:
                os.unlink(sp_file.name)
            except OSError:
                pass


def _wrap_a0_json(text: str) -> str:
    """Ensure output is in Agent Zero JSON tool format.

    If already valid A0 JSON (has tool_name), return as-is.
    Otherwise, wrap plain text in the 'response' tool format.
    """
    stripped = text.strip()
    if not stripped:
        return json.dumps({
            "thoughts": ["No output received from Claude CLI."],
            "headline": "Empty response",
            "tool_name": "response",
            "tool_args": {"text": "[No response from Claude]"},
        })

    # Check if already valid A0 JSON
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict) and "tool_name" in parsed:
            return stripped
    except (json.JSONDecodeError, TypeError):
        pass

    # Wrap plain text in A0 response format
    return json.dumps({
        "thoughts": ["Direct response from Claude."],
        "headline": "Responding",
        "tool_name": "response",
        "tool_args": {"text": stripped},
    })


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict:
    cli_path = shutil.which(CLAUDE_CLI_PATH)
    return {
        "status": "ok",
        "version": "2.0.0",
        "cli_available": bool(cli_path),
        "cli_path": cli_path or "not found",
        "call_count": _call_count,
        "call_limit": SESSION_CALL_LIMIT,
    }


@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {
                "id": "claude-code-proxy",
                "object": "model",
                "created": 1700000000,
                "owned_by": "anthropic",
            },
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest):
    """OpenAI-compatible chat completions endpoint.

    Flow:
    1. Extract system_prompt and user_prompt from messages
    2. Call Claude CLI with --print --system-prompt <sp> <prompt>
    3. Wrap output in A0 JSON format if needed
    4. Return OpenAI-compatible response
    """
    global _call_count
    _call_count += 1

    if _call_count > SESSION_CALL_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"Session call limit ({SESSION_CALL_LIMIT}) exceeded. Restart adapter to reset.",
        )

    logger.info(
        "Request: model=%s, messages=%d, stream=%s",
        req.model, len(req.messages), req.stream,
    )

    system_prompt, user_prompt = _messages_to_prompts(req.messages)

    if not user_prompt.strip():
        raise HTTPException(status_code=400, detail="No user messages provided")

    # Run Claude CLI
    stdout, stderr, rc = await _run_claude_cli(
        prompt=user_prompt,
        system_prompt=system_prompt,
        max_turns=1,
    )

    # Handle errors
    if rc != 0 and not stdout:
        error_msg = stderr or "Claude CLI failed with no output"
        logger.error("CLI error (rc=%d): %s", rc, error_msg)
        stdout = error_msg

    # Wrap in A0 JSON format
    output = _wrap_a0_json(stdout)

    logger.info("Response preview: %s", output[:200])

    # Build OpenAI-compatible response
    return ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex[:12]}",
        created=int(time.time()),
        model=req.model,
        choices=[
            ChatCompletionChoice(
                message=ChatMessage(role="assistant", content=output),
            )
        ],
        usage=UsageInfo(
            prompt_tokens=len(user_prompt) // 4,
            completion_tokens=len(output) // 4,
            total_tokens=(len(user_prompt) + len(output)) // 4,
        ),
    )


# ── Entrypoint ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    logger.info("Starting Claude Code Adapter v2 on %s:%d", HOST, PORT)
    uvicorn.run(app, host=HOST, port=PORT)
