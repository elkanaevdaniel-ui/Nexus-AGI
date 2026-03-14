"""Model configurations, costs, tier assignments, and fallback chains."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from .models import ModelConfig, ModelTier, Provider

# ---------------------------------------------------------------------------
# Provider API configuration (keys loaded from environment)
# ---------------------------------------------------------------------------

def get_provider_env() -> dict[Provider, dict[str, str]]:
    """Return provider connection details from environment variables."""
    return {
        Provider.ANTHROPIC: {
            "api_key": os.environ.get("ANTHROPIC_API_KEY", ""),
            "base_url": "https://api.anthropic.com/v1",
        },
        Provider.OPENROUTER: {
            "api_key": os.environ.get("OPENROUTER_API_KEY", ""),
            "base_url": "https://openrouter.ai/api/v1",
        },
        Provider.GOOGLE_GEMINI: {
            "api_key": os.environ.get("GOOGLE_API_KEY", ""),
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
        },
        Provider.DEEPSEEK: {
            "api_key": os.environ.get("DEEPSEEK_API_KEY", ""),
            "base_url": "https://api.deepseek.com/v1",
            },
        Provider.NVIDIA_NIM: {
            "api_key": os.environ.get("NVIDIA_API_KEY", ""),
            "base_url": "https://integrate.api.nvidia.com/v1",
        },
    },
        },
        Provider.NVIDIA_NIM: {
            "api_key": os.environ.get("NVIDIA_API_KEY", ""),
            "base_url": "https://integrate.api.nvidia.com/v1",
        },
    }


# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------

ALL_MODELS: list[ModelConfig] = [
    # --- FAST tier ---
    ModelConfig(
        model_id="gemini-2.5-flash",
        display_name="Gemini 2.5 Flash",
        provider=Provider.GOOGLE_GEMINI,
        tier=ModelTier.FAST,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
        max_context_tokens=1_000_000,
        supports_vision=True,
    ),
    ModelConfig(
        model_id="gemini-1.5-flash",
        display_name="Gemini 1.5 Flash",
        provider=Provider.GOOGLE_GEMINI,
        tier=ModelTier.FAST,
        cost_per_1k_input=0.000075,
        cost_per_1k_output=0.0003,
        max_context_tokens=1_000_000,
        supports_vision=True,
    ),
    ModelConfig(
        model_id="claude-haiku-4-5",
        display_name="Claude Haiku 4.5",
        provider=Provider.ANTHROPIC,
        tier=ModelTier.FAST,
        cost_per_1k_input=0.0008,
        cost_per_1k_output=0.004,
        max_context_tokens=200_000,
        supports_vision=True,
    ),
    ModelConfig(
        model_id="gpt-4o-mini",
        display_name="GPT-4o Mini",
        provider=Provider.OPENROUTER,
        tier=ModelTier.FAST,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
        max_context_tokens=128_000,
        supports_vision=True,
    ),
    ModelConfig(
        model_id="deepseek-chat",
        display_name="DeepSeek V3",
        provider=Provider.DEEPSEEK,
        tier=ModelTier.FAST,
        cost_per_1k_input=0.00014,
        cost_per_1k_output=0.00028,
        max_context_tokens=128_000,
    ),
    # --- BALANCED tier ---
    ModelConfig(
        model_id="claude-sonnet-4-20250514",
        display_name="Claude Sonnet 4",
        provider=Provider.ANTHROPIC,
        tier=ModelTier.BALANCED,
        cost_per_1k_input=0.003,
        cost_per_1k_output=0.015,
        max_context_tokens=200_000,
        supports_vision=True,
    ),
    ModelConfig(
        model_id="gemini-2.5-pro",
        display_name="Gemini 2.5 Pro",
        provider=Provider.GOOGLE_GEMINI,
        tier=ModelTier.BALANCED,
        cost_per_1k_input=0.00125,
        cost_per_1k_output=0.01,
        max_context_tokens=1_000_000,
        supports_vision=True,
    ),
    ModelConfig(
        model_id="gpt-4o",
        display_name="GPT-4o",
        provider=Provider.OPENROUTER,
        tier=ModelTier.BALANCED,
        cost_per_1k_input=0.0025,
        cost_per_1k_output=0.01,
        max_context_tokens=128_000,
        supports_vision=True,
    ),
    # --- DEEP tier ---
    ModelConfig(
        model_id="claude-opus-4-20250514",
        display_name="Claude Opus 4",
        provider=Provider.ANTHROPIC,
        tier=ModelTier.DEEP,
        cost_per_1k_input=0.015,
        cost_per_1k_output=0.075,
        max_context_tokens=200_000,
        supports_vision=True,
    ),
    ModelConfig(
        model_id="o1",
        display_name="OpenAI o1",
        provider=Provider.OPENROUTER,
        tier=ModelTier.DEEP,
        cost_per_1k_input=0.015,
        cost_per_1k_output=0.06,
        max_context_tokens=200_000,
    ),
    ModelConfig(
        model_id="deepseek-reasoner",
        display_name="DeepSeek R1",
        provider=Provider.DEEPSEEK,
        tier=ModelTier.DEEP,
        cost_per_1k_input=0.00055,
        cost_per_1k_output=0.0022,
        max_context_tokens=128_000,
    ),
    ModelConfig(
        model_id="nvidia/nemotron-3-super-120b-a12b-fast",
        display_name="Nemotron 3 Super (Fast)",
        provider=Provider.NVIDIA_NIM,
        tier=ModelTier.FAST,
        cost_per_1k_input=0.0003,
        cost_per_1k_output=0.0012,
        max_context_tokens=128_000,
        supports_vision=False,
    ),
    ModelConfig(
        model_id="nvidia/nemotron-3-super-120b-a12b",
        display_name="Nemotron 3 Super",
        provider=Provider.NVIDIA_NIM,
        tier=ModelTier.DEEP,
        cost_per_1k_input=0.0003,
        cost_per_1k_output=0.0012,
        max_context_tokens=1_000_000,
        supports_vision=False,
    ),
]

# ---------------------------------------------------------------------------
# Fallback chains — ordered lists per tier
# ---------------------------------------------------------------------------

FALLBACK_CHAINS: dict[ModelTier, list[str]] = {
    ModelTier.FAST: [
        "nvidia/nemotron-3-super-120b-a12b-fast",
        "gemini-2.5-flash",
        "gemini-1.5-flash",
        "claude-haiku-4-5",
        "gpt-4o-mini",
        "deepseek-chat",
    ],
    ModelTier.BALANCED: [
        "claude-sonnet-4-20250514",
        "gemini-2.5-pro",
        "gpt-4o",
    ],
    ModelTier.DEEP: [
        "claude-opus-4-20250514",
        "o1",
        "deepseek-reasoner",
        "nvidia/nemotron-3-super-120b-a12b",
    ],
}

# ---------------------------------------------------------------------------
# Provider rate limits (requests per minute)
# ---------------------------------------------------------------------------

PROVIDER_RATE_LIMITS: dict[Provider, int] = {
    Provider.ANTHROPIC: 60,
    Provider.OPENROUTER: 200,
    Provider.GOOGLE_GEMINI: 360,
    Provider.DEEPSEEK: 120,
    Provider.NVIDIA_NIM: 200,
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MODEL_INDEX: dict[str, ModelConfig] | None = None


def get_model(model_id: str) -> ModelConfig | None:
    """Look up a model by its ID."""
    global _MODEL_INDEX
    if _MODEL_INDEX is None:
        _MODEL_INDEX = {m.model_id: m for m in ALL_MODELS}
    return _MODEL_INDEX.get(model_id)


def get_models_for_tier(tier: ModelTier) -> list[ModelConfig]:
    """Return all models assigned to a tier."""
    return [m for m in ALL_MODELS if m.tier == tier]


def get_fallback_chain(tier: ModelTier) -> list[ModelConfig]:
    """Return the ordered fallback chain as ModelConfig objects."""
    chain: list[ModelConfig] = []
    for model_id in FALLBACK_CHAINS.get(tier, []):
        model = get_model(model_id)
        if model is not None:
            chain.append(model)
    return chain
