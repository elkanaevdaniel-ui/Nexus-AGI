"""Claude Code Adapter Service — headless FastAPI wrapper around Claude CLI."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import time
import uuid
from enum import Enum
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Config ───────────────────────────────────────────────────────────────────────

API_KEY = os.environ.get("CLAUDE_ADAPTER_API_KEY", "")
CLAUDE_CLI_PATH = os.environ.get("CLAUDE_CODE_CLI_PATH", "claude")
DEFAULT_WORKING_DIR = os.environ.get("CLAUDE_ADAPTER_WORKDIR", os.getcwd())
MAX_TURNS = int(os.environ.get("CLAUDE_ADAPTER_MAX_TURNS", "25"))
HOST = os.environ.get("CLAUDE_ADAPTER_HOST", "0.0.0.0")
PORT = int(os.environ.get("CLAUDE_ADAPTER_PORT", "8090"))

RISKY_PATTERNS = [
    "git push", "rm -rf", "drop table", "delete file",
    "force push", "git reset --hard", "truncate",
]


# ── Models ───────────────────────────────────────────────────────────────────────

class TaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskRequest(BaseModel):
    prompt: str
    working_dir: str | None = None
    max_turns: int = Field(default=MAX_TURNS, ge=1, le=100)


class TaskState(BaseModel):
    task_id: str
    status: TaskStatus
    output: str = ""
    pending_approval: str | None = None


# ── OpenAI-compatible models ─────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str | list | None = ""

class ChatCompletionRequest(BaseModel):
    model: str = "claude-sonnet-4-6"
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


# ── In-memory store ──────────────────────────────────────────────────────────────

_tasks: dict[str, TaskState] = {}
_approval_events: dict[str, asyncio.Event] = {}
_approval_decisions: dict[str, bool] = {}


# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(title="Claude Code Adapter", version="1.1.0")

cors_origins = os.environ.get("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in cors_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _verify_api_key(x_api_key: str = Header("")) -> None:
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


# ── Helpers ──────────────────────────────────────────────────────────────────────

def _extract_content(event) -> str:
    if not isinstance(event, dict):
        return str(event) if event else ""
    event_type = event.get("type", "")
    if event_type == "assistant":
        content = event.get("content", "")
        if isinstance(content, list):
            return "".join(
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            )
        return str(content) if content else ""
    if event_type == "result":
        result = event.get("result", "")
        return str(result) if isinstance(result, str) else ""
    return ""


async def _run_claude_task(task_id: str, prompt: str, working_dir: str, max_turns: int) -> None:
    task = _tasks[task_id]
    task.status = TaskStatus.RUNNING

    cli_path = shutil.which(CLAUDE_CLI_PATH) or CLAUDE_CLI_PATH
    cmd = [
        cli_path,
        "--print",
        "--max-turns", str(max_turns),
    ]
    if system_prompt:
        cmd.extend(["--system-prompt", system_prompt])
    cmd.append(prompt)

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.DEVNULL,
            cwd=working_dir,
        )

        assert process.stdout is not None
        async for raw_line in process.stdout:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                content = _extract_content(event) if isinstance(event, dict) else str(event)
            except json.JSONDecodeError:
                content = line

            if content:
                task.output += content

                # Check for risky actions
                lower = content.lower()
                for pattern in RISKY_PATTERNS:
                    if pattern in lower:
                        task.status = TaskStatus.AWAITING_APPROVAL
                        task.pending_approval = pattern
                        evt = asyncio.Event()
                        _approval_events[task_id] = evt
                        logger.info("Task %s awaiting approval for: %s", task_id, pattern)
                        await evt.wait()
                        approved = _approval_decisions.pop(task_id, False)
                        _approval_events.pop(task_id, None)
                        if not approved:
                            task.status = TaskStatus.FAILED
                            task.output += f"\n[DENIED] Action '{pattern}' was rejected by user."
                            process.terminate()
                            return
                        task.status = TaskStatus.RUNNING
                        task.pending_approval = None
                        break

        await process.wait()

        if process.returncode != 0 and process.stderr:
            stderr_bytes = await process.stderr.read()
            stderr_text = stderr_bytes.decode("utf-8", errors="replace").strip()
            if stderr_text:
                logger.error("Claude CLI stderr: %s", stderr_text)
                task.output += f"\n[stderr] {stderr_text}"

        task.status = TaskStatus.COMPLETED

    except FileNotFoundError:
        task.status = TaskStatus.FAILED
        task.output = "Claude CLI not found. Ensure 'claude' is in PATH."
        logger.error("Claude CLI not found at: %s", cli_path)
    except Exception as exc:
        task.status = TaskStatus.FAILED
        task.output += f"\n[error] {exc}"
        logger.exception("Task %s failed", task_id)


# ── SSE stream ───────────────────────────────────────────────────────────────────

async def _sse_generator(task_id: str) -> AsyncGenerator[str, None]:
    last_len = 0
    while True:
        task = _tasks.get(task_id)
        if task is None:
            yield f"event: error\ndata: {json.dumps({'error': 'task not found'})}\n\n"
            return

        current_len = len(task.output)
        if current_len > last_len:
            chunk = task.output[last_len:current_len]
            yield f"event: chunk\ndata: {json.dumps({'text': chunk})}\n\n"
            last_len = current_len

        if task.status == TaskStatus.AWAITING_APPROVAL:
            yield f"event: approval_required\ndata: {json.dumps({'action': task.pending_approval})}\n\n"

        if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            yield f"event: done\ndata: {json.dumps({'status': task.status.value, 'output_length': len(task.output)})}\n\n"
            return

        await asyncio.sleep(0.3)


# ── OpenAI-compatible helper ───────────────────────────────────────────────────────

def _messages_to_prompt(messages: list[ChatMessage]) -> tuple[str, str]:
    """Convert OpenAI-style messages array to a single prompt string for Claude CLI."""
    sp, up = [], []
    for msg in messages:
        _c = msg.content
        if isinstance(_c, list):
            msg.content = " ".join(b.get("text","") if isinstance(b,dict) else str(b) for b in _c)
        elif not isinstance(_c, str):
            msg.content = str(_c or "")
        if msg.role == "system":
            sp.append(msg.content)
        elif msg.role == "user":
            up.append(msg.content)
        elif msg.role == "assistant":
            up.append(f"[Previous assistant response]: {msg.content}")
    return "\n\n".join(sp), "\n\n".join(up)


async def _run_claude_sync(prompt: str, max_turns: int = 5, system_prompt: str = "") -> str:
    """Run Claude CLI synchronously (wait for completion) and return the output text."""
    cli_path = shutil.which(CLAUDE_CLI_PATH) or CLAUDE_CLI_PATH
    cmd = [
        cli_path,
        "--print",
        "--max-turns", str(max_turns),
    ]

    if system_prompt:
        cmd.extend(["--system-prompt", system_prompt])
    cmd.append(prompt)
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.DEVNULL,
            cwd=DEFAULT_WORKING_DIR,
        )

        output_parts = []
        assert process.stdout is not None
        async for raw_line in process.stdout:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                content = _extract_content(event) if isinstance(event, dict) else str(event)
            except json.JSONDecodeError:
                content = line
            if content:
                output_parts.append(content)

        await process.wait()

        if process.returncode != 0 and process.stderr:
            stderr_bytes = await process.stderr.read()
            stderr_text = stderr_bytes.decode("utf-8", errors="replace").strip()
            if stderr_text and not output_parts:
                return f"[Error] {stderr_text}"

        return "".join(output_parts) or "[No output from Claude CLI]"

    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Claude CLI not found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


async def _stream_claude_sse(prompt: str, model: str, max_turns: int = 5, system_prompt: str = "") -> AsyncGenerator[str, None]:
    """Stream Claude CLI output as OpenAI-compatible SSE chunks."""
    cli_path = shutil.which(CLAUDE_CLI_PATH) or CLAUDE_CLI_PATH
    cmd = [
        cli_path,
        "--print",
        "--max-turns", str(max_turns),
    ]
    if system_prompt:
        cmd.extend(["--system-prompt", system_prompt])
    cmd.append(prompt)

    completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    created = int(time.time())

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.DEVNULL,
            cwd=DEFAULT_WORKING_DIR,
        )

        assert process.stdout is not None
        async for raw_line in process.stdout:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                content = _extract_content(event) if isinstance(event, dict) else str(event)
            except json.JSONDecodeError:
                content = line

            if content:
                chunk = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "delta": {"content": content},
                        "finish_reason": None,
                    }],
                }
                yield f"data: {json.dumps(chunk)}\n\n"

        # Send final chunk with finish_reason
        final_chunk = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {},
                "finish_reason": "stop",
            }],
        }
        yield f"data: {json.dumps(final_chunk)}\n\n"
        yield "data: [DONE]\n\n"

    except Exception as exc:
        error_chunk = {
            "error": {"message": str(exc), "type": "server_error"},
        }
        yield f"data: {json.dumps(error_chunk)}\n\n"
        yield "data: [DONE]\n\n"


# ── Routes ───────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict[str, str]:
    cli_path = shutil.which(CLAUDE_CLI_PATH)
    return {
        "status": "ok",
        "cli_available": "yes" if cli_path else "no",
        "cli_path": cli_path or "not found",
    }


# ── OpenAI-compatible endpoints ────────────────────────────────────────────────────

@app.get("/v1/models")
async def list_models():
    """OpenAI-compatible model listing."""
    return {
        "object": "list",
        "data": [
            {
                "id": "claude-opus-4-6",
                "object": "model",
                "created": 1700000000,
                "owned_by": "anthropic",
            },
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest):
    """
    OpenAI-compatible chat completions endpoint.

    Translates OpenAI chat format -> Claude CLI prompt -> OpenAI response format.
    This allows Agent Zero (via LiteLLM) to talk to Claude CLI through the sub plan.
    """
    logger.info("OpenAI-compat request: model=%s, messages=%d, stream=%s",
                req.model, len(req.messages), req.stream)

    system_prompt, user_prompt = _messages_to_prompt(req.messages)

    if not user_prompt.strip():
        raise HTTPException(status_code=400, detail="No messages provided")

    max_turns = 1  # Single turn for fast chat completions

    # DISABLED: if req.stream:
    # DISABLED: # Use sync call and wrap as SSE (streaming CLI removed for speed)
    # DISABLED: sync_output = await _run_claude_sync(user_prompt, max_turns, system_prompt=system_prompt)
    # DISABLED: import uuid as _uuid
    # DISABLED: async def _fake_stream():
    # DISABLED: chunk = {
    # DISABLED: 'id': f'chatcmpl-{_uuid.uuid4().hex[:12]}',
    # DISABLED: 'object': 'chat.completion.chunk',
    # DISABLED: 'created': int(__import__('time').time()),
    # DISABLED: 'model': req.model,
    # DISABLED: 'choices': [{'index': 0, 'delta': {'role': 'assistant', 'content': sync_output}, 'finish_reason': 'stop'}],
    # DISABLED: }
    # DISABLED: yield f'data: {json.dumps(chunk)}\n\n'
    # DISABLED: yield 'data: [DONE]\n\n'
    # DISABLED: return StreamingResponse(
    # DISABLED: _fake_stream(),
    # DISABLED: media_type="text/event-stream",
    # DISABLED: )

    # Synchronous mode: run Claude CLI and wait for full output
    output = await _run_claude_sync(user_prompt, max_turns, system_prompt=system_prompt)

    # Fallback: wrap plain text in Agent Zero JSON format
    _os = output.strip()
    if _os:
        try:
            _pp = json.loads(_os)
            if not (isinstance(_pp, dict) and "tool_name" in _pp): raise ValueError()
        except Exception:
            output = json.dumps({"thoughts":["Direct response."],"headline":"Responding to user","tool_name":"response","tool_args":{"text":_os}})

    completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    return ChatCompletionResponse(
        id=completion_id,
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


# ── Original task-based routes ─────────────────────────────────────────────────────

@app.post("/task", response_model=TaskState)
async def create_task(req: TaskRequest, x_api_key: str = Header("")) -> TaskState:
    _verify_api_key(x_api_key)
    task_id = str(uuid.uuid4())
    working_dir = req.working_dir or DEFAULT_WORKING_DIR

    task = TaskState(task_id=task_id, status=TaskStatus.QUEUED)
    _tasks[task_id] = task

    asyncio.create_task(_run_claude_task(task_id, req.prompt, working_dir, req.max_turns))
    return task


@app.get("/task/{task_id}", response_model=TaskState)
async def get_task(task_id: str, x_api_key: str = Header("")) -> TaskState:
    _verify_api_key(x_api_key)
    task = _tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.get("/task/{task_id}/stream")
async def stream_task(task_id: str, x_api_key: str = Header("")) -> StreamingResponse:
    _verify_api_key(x_api_key)
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return StreamingResponse(_sse_generator(task_id), media_type="text/event-stream")


@app.post("/task/{task_id}/approve")
async def approve_task(task_id: str, x_api_key: str = Header("")) -> dict[str, str]:
    _verify_api_key(x_api_key)
    evt = _approval_events.get(task_id)
    if evt is None:
        raise HTTPException(status_code=404, detail="No pending approval for this task")
    _approval_decisions[task_id] = True
    evt.set()
    return {"status": "approved"}


@app.post("/task/{task_id}/deny")
async def deny_task(task_id: str, x_api_key: str = Header("")) -> dict[str, str]:
    _verify_api_key(x_api_key)
    evt = _approval_events.get(task_id)
    if evt is None:
        raise HTTPException(status_code=404, detail="No pending approval for this task")
    _approval_decisions[task_id] = False
    evt.set()
    return {"status": "denied"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
