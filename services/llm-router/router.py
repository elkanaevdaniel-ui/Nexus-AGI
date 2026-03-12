"""Unified LLM router — replaces 5 duplicate routing systems.

Tier-based routing (FAST/BALANCED/DEEP), task classification, fallback
chains, cost tracking, provider circuit-breaking, and improved token estimation.
"""
from __future__ import annotations

import logging, re, time, unicodedata
from typing import Any

import httpx

from .config import get_fallback_chain, get_provider_env
from .models import (
    LLMResponse, ModelConfig, ModelTier, Provider, ProviderHealth,
    RoutingContext, RoutingResult, TaskClassification, TaskType,
)

logger = logging.getLogger(__name__)

# -- Token estimation (fixes naive word_count*1.3 bug) ----------------------

_SCRIPT_TOKEN_RATIOS: dict[str, float] = {
    "CJK": 2.5, "HANGUL": 1.8, "HIRAGANA": 2.0, "KATAKANA": 2.0,
    "THAI": 2.2, "ARABIC": 1.6, "DEVANAGARI": 1.7, "CYRILLIC": 1.5,
    "LATIN": 1.3,
}

_MAX_TOKEN_ESTIMATE = 2_000_000


def _dominant_script(text: str, sample_size: int = 200) -> str:
    """Detect the dominant Unicode script block in *text*."""
    counts: dict[str, int] = {}
    for i, ch in enumerate(c for c in text if c.strip()):
        if i >= sample_size:
            break
        name = unicodedata.name(ch, "")
        matched = next((s for s in _SCRIPT_TOKEN_RATIOS if s in name), "LATIN")
        counts[matched] = counts.get(matched, 0) + 1
    return max(counts, key=counts.__getitem__) if counts else "LATIN"


def estimate_tokens(text: str) -> int:
    """Language-aware token estimation (fixes old word_count*1.3 bug)."""
    if not text:
        return 0
    script = _dominant_script(text)
    ratio = _SCRIPT_TOKEN_RATIOS.get(script, 1.3)
    if script in ("CJK", "HIRAGANA", "KATAKANA", "THAI"):
        estimate = int(sum(1 for ch in text if not ch.isspace()) * ratio)
    else:
        estimate = int(len(text.split()) * ratio)
    return min(estimate, _MAX_TOKEN_ESTIMATE)


# -- Task classification (replaces regex/smart/multi-tier routers) -----------

_COMPLEXITY_KEYWORDS: dict[str, tuple[TaskType, float]] = {
    r"(?i)\b(prove|derive|theorem|formal proof)\b": (TaskType.MATH, 0.9),
    r"(?i)\b(architect|design system|distributed)\b": (TaskType.CODE_GENERATION, 0.85),
    r"(?i)\b(research|in-depth analysis|comprehensive)\b": (TaskType.ANALYSIS, 0.8),
    r"(?i)\b(debate|compare and contrast|evaluate trade-?offs)\b": (TaskType.REASONING, 0.8),
    r"(?i)\b(consensus|multi-model|cross-validate)\b": (TaskType.CONSENSUS, 0.85),
    r"(?i)\b(write code|implement|function|refactor)\b": (TaskType.CODE_GENERATION, 0.55),
    r"(?i)\b(summarize|summary|tldr)\b": (TaskType.SUMMARIZATION, 0.35),
    r"(?i)\b(classify|categorize|label)\b": (TaskType.CLASSIFICATION, 0.3),
    r"(?i)\b(explain|analyze|why)\b": (TaskType.ANALYSIS, 0.5),
    r"(?i)\b(write|draft|compose|story|poem)\b": (TaskType.CREATIVE_WRITING, 0.5),
    r"(?i)\b(calculate|solve|equation|math)\b": (TaskType.MATH, 0.55),
    r"(?i)\b(translate|convert|format)\b": (TaskType.GENERAL, 0.25),
    r"(?i)\b(what is|define|who is|when did)\b": (TaskType.SIMPLE_QA, 0.15),
    r"(?i)\b(list|enumerate|name)\b": (TaskType.SIMPLE_QA, 0.2),
}
_TIER_THRESHOLDS = (0.35, 0.7)  # < FAST | < BALANCED | DEEP


def classify_task(task: str) -> TaskClassification:
    """Classify a task by type and complexity using keyword + length heuristics."""
    best_type, best_complexity = TaskType.GENERAL, 0.3
    for pattern, (task_type, complexity) in _COMPLEXITY_KEYWORDS.items():
        if re.search(pattern, task) and complexity > best_complexity:
            best_type, best_complexity = task_type, complexity

    wc = len(task.split())
    if wc > 500:
        best_complexity = min(1.0, best_complexity + 0.15)
    elif wc > 200:
        best_complexity = min(1.0, best_complexity + 0.08)

    if best_complexity < _TIER_THRESHOLDS[0]:
        tier = ModelTier.FAST
    elif best_complexity < _TIER_THRESHOLDS[1]:
        tier = ModelTier.BALANCED
    else:
        tier = ModelTier.DEEP

    return TaskClassification(
        task_type=best_type, complexity=round(best_complexity, 3),
        recommended_tier=tier,
        reasoning=f"type={best_type.value}, complexity={best_complexity:.2f}",
    )


# -- Router ------------------------------------------------------------------

class LLMRouter:
    """Unified LLM router with tier-based routing, fallbacks, and cost tracking."""

    def __init__(self) -> None:
        self._provider_health: dict[Provider, ProviderHealth] = {
            p: ProviderHealth(provider=p) for p in Provider
        }
        self._total_cost_usd: float = 0.0
        self._http: httpx.AsyncClient | None = None

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=120.0)
        return self._http

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()

    async def route(
        self,
        task: str,
        context: dict[str, Any] | None = None,
    ) -> RoutingResult:
        """Main entry point: classify a task and pick the best model + fallbacks."""
        ctx = RoutingContext(**(context or {}))
        classification = classify_task(task)

        # Allow caller to override tier
        tier = ctx.preferred_tier or classification.recommended_tier

        chain = self._build_chain(tier, ctx)
        if not chain:
            # Escalate to next tier if the preferred one is entirely unavailable
            for fallback_tier in (ModelTier.BALANCED, ModelTier.DEEP, ModelTier.FAST):
                if fallback_tier != tier:
                    chain = self._build_chain(fallback_tier, ctx)
                    if chain:
                        break
        if not chain:
            raise RuntimeError("All providers are circuit-broken; no models available")

        selected = chain[0]
        fallbacks = chain[1:]
        input_tokens = estimate_tokens(task)
        est_cost = (input_tokens / 1000) * selected.cost_per_1k_input

        return RoutingResult(
            selected_model=selected,
            fallback_chain=fallbacks,
            classification=classification,
            estimated_input_tokens=input_tokens,
            estimated_cost_usd=round(est_cost, 6),
            budget_remaining_usd=(
                round(ctx.budget_limit_usd - self._total_cost_usd, 6)
                if ctx.budget_limit_usd is not None
                else None
            ),
        )

    async def call_llm(
        self,
        prompt: str,
        task_type: str = "general",
        *,
        context: dict[str, Any] | None = None,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Convenience: route, then call the LLM with automatic fallback."""
        routing = await self.route(prompt, context)
        ctx = RoutingContext(**(context or {}))

        # Budget guard
        if ctx.budget_limit_usd is not None:
            if self._total_cost_usd >= ctx.budget_limit_usd:
                raise RuntimeError(
                    f"Budget exhausted: spent ${self._total_cost_usd:.4f} "
                    f"of ${ctx.budget_limit_usd:.4f}"
                )

        all_models = [routing.selected_model, *routing.fallback_chain]
        last_error: Exception | None = None

        for model in all_models:
            health = self._provider_health[model.provider]
            if not health.is_available():
                logger.warning("Skipping %s — circuit open", model.provider.value)
                continue
            try:
                response = await self._call_provider(model, prompt, max_tokens)
                health.record_success()
                # Track cost
                cost = self._compute_cost(model, response)
                self._total_cost_usd += cost
                response.cost_usd = round(cost, 6)
                return response
            except Exception as exc:
                last_error = exc
                health.record_error(str(exc))
                logger.error(
                    "Provider %s model %s failed: %s",
                    model.provider.value,
                    model.model_id,
                    exc,
                )

        raise RuntimeError(
            f"All models in the fallback chain failed. Last error: {last_error}"
        )

    def _build_chain(
        self, tier: ModelTier, ctx: RoutingContext
    ) -> list[ModelConfig]:
        """Build an ordered model chain, filtering by health and requirements."""
        chain = get_fallback_chain(tier)
        result: list[ModelConfig] = []
        for m in chain:
            health = self._provider_health[m.provider]
            if not health.is_available():
                continue
            if ctx.require_vision and not m.supports_vision:
                continue
            if ctx.require_tools and not m.supports_tools:
                continue
            if ctx.preferred_provider and m.provider == ctx.preferred_provider:
                result.insert(0, m)  # Preferred provider goes first
            else:
                result.append(m)
        return result

    async def _call_provider(
        self,
        model: ModelConfig,
        prompt: str,
        max_tokens: int,
    ) -> LLMResponse:
        """Dispatch an LLM call to the correct provider API."""
        env = get_provider_env()
        conf = env.get(model.provider, {})
        api_key = conf.get("api_key", "")
        base_url = conf.get("base_url", "")

        if not api_key:
            raise ValueError(
                f"No API key configured for provider {model.provider.value}"
            )

        client = await self._client()
        start = time.monotonic()

        if model.provider == Provider.ANTHROPIC:
            resp = await self._call_anthropic(client, base_url, api_key, model, prompt, max_tokens)
        elif model.provider == Provider.GOOGLE_GEMINI:
            resp = await self._call_gemini(client, base_url, api_key, model, prompt, max_tokens)
        elif model.provider in (Provider.OPENROUTER, Provider.DEEPSEEK):
            resp = await self._call_openai_compat(client, base_url, api_key, model, prompt, max_tokens)
        else:
            raise ValueError(f"Unsupported provider: {model.provider}")

        resp.latency_ms = round((time.monotonic() - start) * 1000, 1)
        return resp

    async def _call_anthropic(
        self, client: httpx.AsyncClient, base_url: str, api_key: str,
        model: ModelConfig, prompt: str, max_tokens: int,
    ) -> LLMResponse:
        r = await client.post(
            f"{base_url}/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model.model_id,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        r.raise_for_status()
        data = r.json()
        text = data.get("content", [{}])[0].get("text", "")
        usage = data.get("usage", {})
        return LLMResponse(
            text=text,
            model_used=model.model_id,
            provider=model.provider,
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
        )

    async def _call_gemini(
        self, client: httpx.AsyncClient, base_url: str, api_key: str,
        model: ModelConfig, prompt: str, max_tokens: int,
    ) -> LLMResponse:
        url = (
            f"{base_url}/models/{model.model_id}:generateContent"
            f"?key={api_key}"
        )
        r = await client.post(
            url,
            headers={"content-type": "application/json"},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"maxOutputTokens": max_tokens},
            },
        )
        r.raise_for_status()
        data = r.json()
        candidates = data.get("candidates", [{}])
        text = (
            candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            if candidates
            else ""
        )
        usage = data.get("usageMetadata", {})
        return LLMResponse(
            text=text,
            model_used=model.model_id,
            provider=model.provider,
            input_tokens=usage.get("promptTokenCount"),
            output_tokens=usage.get("candidatesTokenCount"),
        )

    async def _call_openai_compat(
        self, client: httpx.AsyncClient, base_url: str, api_key: str,
        model: ModelConfig, prompt: str, max_tokens: int,
    ) -> LLMResponse:
        """OpenAI-compatible endpoint (OpenRouter, DeepSeek)."""
        r = await client.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "content-type": "application/json",
            },
            json={
                "model": model.model_id,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        r.raise_for_status()
        data = r.json()
        choices = data.get("choices", [{}])
        text = choices[0].get("message", {}).get("content", "") if choices else ""
        usage = data.get("usage", {})
        return LLMResponse(
            text=text,
            model_used=model.model_id,
            provider=model.provider,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
        )

    @staticmethod
    def _compute_cost(model: ModelConfig, response: LLMResponse) -> float:
        input_t = response.input_tokens or 0
        output_t = response.output_tokens or 0
        return (
            (input_t / 1000) * model.cost_per_1k_input
            + (output_t / 1000) * model.cost_per_1k_output
        )

    @property
    def total_cost_usd(self) -> float:
        return round(self._total_cost_usd, 6)

    def get_provider_health(self, provider: Provider) -> ProviderHealth:
        return self._provider_health[provider]


# -- Module-level convenience (singleton) ------------------------------------

_default_router: LLMRouter | None = None


def _get_router() -> LLMRouter:
    global _default_router
    if _default_router is None:
        _default_router = LLMRouter()
    return _default_router


async def route(task: str, context: dict[str, Any] | None = None) -> RoutingResult:
    """Module-level shortcut — route a task to the best model."""
    return await _get_router().route(task, context)


async def call_llm(prompt: str, task_type: str = "general", **kwargs: Any) -> LLMResponse:
    """Module-level shortcut — route and call in one step."""
    return await _get_router().call_llm(prompt, task_type, **kwargs)
