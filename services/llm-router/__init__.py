"""Unified LLM Router — Nexus-AGI project.

Replaces five duplicate routing systems:
  1. ai-projects/linkedin-bot/smart_router.py
  2. ai-projects/orchestrator/router.py
  3. ai-projects/cost-optimizer/core/router.py
  4. polymarket-agent's implicit routing in probability.py
  5. ai-projects/multi_tier_router.py

Usage::

    from services.llm_router import route, call_llm, classify_task, estimate_tokens

    # Classify a task to see which tier it maps to
    classification = classify_task("Prove the Riemann hypothesis")

    # Route without calling (inspect the model selection)
    result = await route("Summarize this article", context={"budget_limit_usd": 0.50})

    # Route and call in one shot
    response = await call_llm("Write a haiku about Python")
"""

from .models import (
    LLMResponse,
    ModelConfig,
    ModelTier,
    Provider,
    ProviderHealth,
    RoutingContext,
    RoutingResult,
    TaskClassification,
    TaskType,
)
from .router import (
    LLMRouter,
    call_llm,
    classify_task,
    estimate_tokens,
    route,
)

__all__ = [
    # Core functions
    "route",
    "call_llm",
    "classify_task",
    "estimate_tokens",
    # Router class
    "LLMRouter",
    # Models
    "LLMResponse",
    "ModelConfig",
    "ModelTier",
    "Provider",
    "ProviderHealth",
    "RoutingContext",
    "RoutingResult",
    "TaskClassification",
    "TaskType",
]
