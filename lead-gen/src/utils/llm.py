"""LLM provider utility — uses Anthropic Claude via langchain_core."""

from langchain_core.language_models import BaseChatModel

from src.config import settings


def get_llm() -> BaseChatModel:
    """Get the configured LLM instance for scoring and outreach generation."""
    from langchain_core.language_models.chat_models import BaseChatModel

    if settings.anthropic_api_key:
        from langchain_core.messages import AIMessage

        return _get_anthropic_llm()

    raise RuntimeError(
        "No LLM API key configured. Set ANTHROPIC_API_KEY in your .env file."
    )


def _get_anthropic_llm() -> BaseChatModel:
    """Create an Anthropic Claude LLM instance."""
    try:
        from langchain_anthropic import ChatAnthropic
    except ImportError:
        raise RuntimeError(
            "langchain-anthropic is required. Install it: pip install langchain-anthropic"
        )

    model_id = "claude-haiku-4-5-20251001"
    llm_model = settings.llm_model
    if "sonnet" in llm_model:
        model_id = "claude-sonnet-4-5-20250929"
    elif "opus" in llm_model:
        model_id = "claude-opus-4-6"

    return ChatAnthropic(
        model=model_id,
        api_key=settings.anthropic_api_key,
        max_tokens=1024,
        temperature=0.3,
    )
