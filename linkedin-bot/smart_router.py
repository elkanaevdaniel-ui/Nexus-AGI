"""
smart_router.py — Smart AI Model Router for NEXUS
Routes tasks to the cheapest capable model:
  - Free/cheap models (Gemini Flash, GPT-3.5) for simple tasks
  - Mid-tier (Claude Haiku, GPT-4o-mini) for moderate tasks
  - Premium (Claude Opus 4.6) for complex coding & hard tasks
"""
import json
import logging
import re
import requests
import time
from dataclasses import dataclass, field
from typing import Optional

from config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, GOOGLE_API_KEY

log = logging.getLogger(__name__)

# ── Model definitions with pricing ────────────────────────────────────────────

MODELS = {
    "free": {
        "id": "google/gemini-2.5-flash:free",
        "name": "Gemini 2.5 Flash (Free)",
        "input_cost": 0.0,
        "output_cost": 0.0,
        "provider": "openrouter",
        "max_tokens": 8192,
    },
    "cheap": {
        "id": "anthropic/claude-3-haiku",
        "name": "Claude 3 Haiku",
        "input_cost": 0.25,
        "output_cost": 1.25,
        "provider": "openrouter",
        "max_tokens": 4096,
    },
    "mid": {
        "id": "openai/gpt-4o-mini",
        "name": "GPT-4o Mini",
        "input_cost": 0.15,
        "output_cost": 0.60,
        "provider": "openrouter",
        "max_tokens": 16384,
    },
    "standard": {
        "id": "anthropic/claude-sonnet-4-5-20250929",
        "name": "Claude 4.5 Sonnet",
        "input_cost": 3.00,
        "output_cost": 15.00,
        "provider": "openrouter",
        "max_tokens": 8192,
    },
    "premium": {
        "id": "anthropic/claude-opus-4-6",
        "name": "Claude Opus 4.6",
        "input_cost": 15.00,
        "output_cost": 75.00,
        "provider": "openrouter",
        "max_tokens": 4096,
    },
}

# ── Complexity detection ──────────────────────────────────────────────────────

COMPLEX_PATTERNS = [
    r'\b(implement|architect|design|refactor|optimize|debug)\b',
    r'\b(algorithm|data structure|system design|distributed)\b',
    r'\b(security|vulnerability|exploit|penetration)\b',
    r'\b(machine learning|neural network|deep learning)\b',
    r'\b(complex|advanced|sophisticated|enterprise)\b',
]

SIMPLE_PATTERNS = [
    r'\b(translate|summarize|classify|extract|list)\b',
    r'\b(what is|define|explain simply|how to)\b',
    r'\b(format|convert|parse|validate)\b',
    r'\b(yes or no|true or false|pick one)\b',
]

CODING_PATTERNS = [
    r'\b(code|function|class|module|api|endpoint)\b',
    r'\b(python|javascript|typescript|rust|go|java)\b',
    r'\b(bug|fix|error|exception|traceback)\b',
    r'\b(test|unittest|pytest|spec)\b',
    r'```',
]


@dataclass
class RoutingResult:
    model_key: str
    model_id: str
    model_name: str
    complexity: str  # simple, moderate, complex, expert
    task_type: str   # qa, creative, coding, analysis
    estimated_cost: float
    reasoning: str


def classify_task(prompt: str, context: str = "") -> RoutingResult:
    """Analyze prompt and route to the best model."""
    text = (prompt + " " + context).lower()
    word_count = len(text.split())

    # Score complexity
    complex_score = sum(1 for p in COMPLEX_PATTERNS if re.search(p, text, re.I))
    simple_score = sum(1 for p in SIMPLE_PATTERNS if re.search(p, text, re.I))
    coding_score = sum(1 for p in CODING_PATTERNS if re.search(p, text, re.I))

    # Determine task type
    if coding_score >= 2:
        task_type = "coding"
    elif complex_score >= 2:
        task_type = "analysis"
    elif any(w in text for w in ["write", "create", "generate", "compose"]):
        task_type = "creative"
    else:
        task_type = "qa"

    # Determine complexity
    if simple_score > complex_score and word_count < 100:
        complexity = "simple"
    elif complex_score >= 3 or (coding_score >= 3 and word_count > 200):
        complexity = "expert"
    elif complex_score >= 2 or coding_score >= 2:
        complexity = "complex"
    elif word_count > 150 or complex_score >= 1:
        complexity = "moderate"
    else:
        complexity = "simple"

    # Route to model
    if complexity == "simple":
        model_key = "free"
    elif complexity == "moderate":
        if task_type == "coding":
            model_key = "mid"
        else:
            model_key = "cheap"
    elif complexity == "complex":
        if task_type == "coding":
            model_key = "standard"
        else:
            model_key = "mid"
    else:  # expert
        model_key = "premium"

    model = MODELS[model_key]
    # Rough token estimate
    est_input = word_count * 1.3
    est_output = min(est_input * 2, model["max_tokens"])
    est_cost = (est_input / 1_000_000 * model["input_cost"] +
                est_output / 1_000_000 * model["output_cost"])

    return RoutingResult(
        model_key=model_key,
        model_id=model["id"],
        model_name=model["name"],
        complexity=complexity,
        task_type=task_type,
        estimated_cost=round(est_cost, 6),
        reasoning=f"{complexity} {task_type} task → {model['name']} (est ${est_cost:.6f})",
    )


def call_ai(prompt: str, system: str = "", context: str = "",
            force_model: str = None, temperature: float = 0.7,
            max_tokens: int = 2000) -> dict:
    """
    Smart AI call — routes to cheapest capable model.
    Returns: {"text": str, "model": str, "cost": float, "tokens": dict}
    """
    if force_model and force_model in MODELS:
        model = MODELS[force_model]
        routing = None
    else:
        routing = classify_task(prompt, context)
        model = MODELS[routing.model_key]

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://nexus-agi.duckdns.org",
        "X-Title": "NEXUS AGI",
    }
    payload = {
        "model": model["id"],
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    start = time.time()
    try:
        resp = requests.post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            headers=headers, json=payload, timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        latency = round((time.time() - start) * 1000, 1)

        text = data["choices"][0]["message"]["content"].strip()
        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        actual_cost = (input_tokens / 1_000_000 * model["input_cost"] +
                       output_tokens / 1_000_000 * model["output_cost"])

        return {
            "text": text,
            "model": model["name"],
            "model_id": model["id"],
            "cost": round(actual_cost, 6),
            "tokens": {"input": input_tokens, "output": output_tokens},
            "latency_ms": latency,
            "routing": routing.reasoning if routing else f"forced: {model['name']}",
        }
    except Exception as exc:
        log.error("AI call failed (%s): %s", model["name"], exc)
        # Fallback to free model if premium fails
        if model["id"] != MODELS["free"]["id"]:
            log.info("Falling back to free model...")
            return call_ai(prompt, system, context, force_model="free",
                           temperature=temperature, max_tokens=max_tokens)
        return {
            "text": f"Error: {exc}",
            "model": model["name"],
            "model_id": model["id"],
            "cost": 0,
            "tokens": {"input": 0, "output": 0},
            "latency_ms": 0,
            "routing": "error fallback",
        }
