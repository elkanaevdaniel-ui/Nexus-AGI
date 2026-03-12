"""Pydantic models for the unified LLM router."""

from __future__ import annotations

import time
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ModelTier(str, Enum):
    """Routing tiers ordered by capability and cost."""

    FAST = "fast"
    BALANCED = "balanced"
    DEEP = "deep"


class Provider(str, Enum):
    """Supported LLM providers."""

    ANTHROPIC = "anthropic"
    OPENROUTER = "openrouter"
    GOOGLE_GEMINI = "google_gemini"
    DEEPSEEK = "deepseek"


class TaskType(str, Enum):
    """Recognized task types for classification."""

    SIMPLE_QA = "simple_qa"
    SUMMARIZATION = "summarization"
    CLASSIFICATION = "classification"
    CODE_GENERATION = "code_generation"
    ANALYSIS = "analysis"
    REASONING = "reasoning"
    CREATIVE_WRITING = "creative_writing"
    MATH = "math"
    CONSENSUS = "consensus"
    GENERAL = "general"


class TaskClassification(BaseModel):
    """Result of classifying a task by complexity."""

    task_type: TaskType = TaskType.GENERAL
    complexity: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="0.0 = trivial, 1.0 = extremely complex",
    )
    recommended_tier: ModelTier = ModelTier.BALANCED
    reasoning: str = ""


class ModelConfig(BaseModel):
    """Configuration for a single model."""

    model_id: str
    display_name: str
    provider: Provider
    tier: ModelTier
    cost_per_1k_input: float = Field(
        description="Cost in USD per 1K input tokens"
    )
    cost_per_1k_output: float = Field(
        description="Cost in USD per 1K output tokens"
    )
    max_context_tokens: int = 128_000
    supports_vision: bool = False
    supports_tools: bool = True


class ProviderHealth(BaseModel):
    """Tracks provider reliability for circuit-breaking."""

    provider: Provider
    error_count: int = 0
    total_calls: int = 0
    last_error_time: float | None = None
    last_error_message: str | None = None
    circuit_open: bool = False
    circuit_opened_at: float | None = None

    # Circuit breaker settings
    error_threshold: int = Field(
        default=5,
        description="Errors within the window before opening circuit",
    )
    circuit_reset_seconds: float = Field(
        default=60.0,
        description="Seconds before half-opening the circuit",
    )

    def record_success(self) -> None:
        self.total_calls += 1
        self.error_count = max(0, self.error_count - 1)
        if self.circuit_open:
            self.circuit_open = False
            self.circuit_opened_at = None

    def record_error(self, message: str = "") -> None:
        now = time.time()
        self.total_calls += 1
        self.error_count += 1
        self.last_error_time = now
        self.last_error_message = message
        if self.error_count >= self.error_threshold:
            self.circuit_open = True
            self.circuit_opened_at = now

    def is_available(self) -> bool:
        """Check if the provider is available (circuit closed or half-open)."""
        if not self.circuit_open:
            return True
        # Allow a retry after the reset period (half-open)
        if self.circuit_opened_at is not None:
            elapsed = time.time() - self.circuit_opened_at
            if elapsed >= self.circuit_reset_seconds:
                return True
        return False


class RoutingResult(BaseModel):
    """Result of the routing decision."""

    selected_model: ModelConfig
    fallback_chain: list[ModelConfig] = Field(default_factory=list)
    classification: TaskClassification
    estimated_input_tokens: int = 0
    estimated_cost_usd: float = 0.0
    budget_remaining_usd: float | None = None


class RoutingContext(BaseModel):
    """Optional context passed to the router to influence decisions."""

    budget_limit_usd: float | None = None
    preferred_provider: Provider | None = None
    preferred_tier: ModelTier | None = None
    require_vision: bool = False
    require_tools: bool = False
    max_tokens: int = 4096
    metadata: dict[str, Any] = Field(default_factory=dict)


class LLMResponse(BaseModel):
    """Wrapper around an LLM call result."""

    text: str
    model_used: str
    provider: Provider
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    latency_ms: float | None = None
