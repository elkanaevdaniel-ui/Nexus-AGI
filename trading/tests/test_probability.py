"""Tests for multi-LLM probability engine and calibration."""

from __future__ import annotations

import pytest
import pytest_asyncio

from src.core.probability import (
    CalibrationTracker,
    calculate_consensus,
    parse_llm_response,
)
from src.data.schemas import LLMProbabilityEstimate


class TestParseLLMResponse:
    """Test LLM response parsing and validation."""

    def test_valid_json(self) -> None:
        """Parse a well-formed JSON response."""
        text = '{"probability": 0.65, "confidence": "medium", "base_rate": 0.5, "factors": [], "reasoning": "test"}'
        result = parse_llm_response(text)
        assert result is not None
        assert result.probability == 0.65
        assert result.confidence == "medium"

    def test_markdown_fenced_json(self) -> None:
        """Parse JSON wrapped in markdown code fences."""
        text = '```json\n{"probability": 0.7, "confidence": "high", "base_rate": 0.5, "factors": [], "reasoning": "r"}\n```'
        result = parse_llm_response(text)
        assert result is not None
        assert result.probability == 0.7

    def test_clamped_to_bounds(self) -> None:
        """Probabilities outside [0.01, 0.99] should be clamped."""
        text = '{"probability": 1.5, "confidence": "high", "base_rate": 0.5, "factors": [], "reasoning": "r"}'
        result = parse_llm_response(text)
        assert result is not None
        assert result.probability == 0.99

    def test_clamped_low(self) -> None:
        text = '{"probability": -0.5, "confidence": "low", "base_rate": 0.5, "factors": [], "reasoning": "r"}'
        result = parse_llm_response(text)
        assert result is not None
        assert result.probability == 0.01

    def test_invalid_json_returns_none(self) -> None:
        result = parse_llm_response("not json at all")
        assert result is None

    def test_missing_fields_returns_none(self) -> None:
        result = parse_llm_response('{"probability": 0.5}')
        assert result is None


class TestCalculateConsensus:
    """Test consensus calculation from multiple estimates."""

    def test_single_estimate(self) -> None:
        est = LLMProbabilityEstimate(
            probability=0.7, confidence="high", base_rate=0.5, reasoning="test"
        )
        result = calculate_consensus([("claude", est)])
        assert abs(result.probability - 0.7) < 0.01
        assert result.claude_estimate == 0.7

    def test_multiple_estimates_averaged(self) -> None:
        e1 = LLMProbabilityEstimate(
            probability=0.6, confidence="medium", base_rate=0.5, reasoning=""
        )
        e2 = LLMProbabilityEstimate(
            probability=0.8, confidence="medium", base_rate=0.5, reasoning=""
        )
        result = calculate_consensus([("claude", e1), ("gemini", e2)])
        assert 0.6 <= result.probability <= 0.8

    def test_high_spread_means_low_confidence(self) -> None:
        e1 = LLMProbabilityEstimate(
            probability=0.3, confidence="high", base_rate=0.5, reasoning=""
        )
        e2 = LLMProbabilityEstimate(
            probability=0.8, confidence="high", base_rate=0.5, reasoning=""
        )
        result = calculate_consensus([("claude", e1), ("gpt", e2)])
        assert result.confidence == "low"
        assert result.spread > 0.20

    def test_empty_returns_default(self) -> None:
        result = calculate_consensus([])
        assert result.probability == 0.5
        assert result.confidence == "low"


class TestOpenRouterIntegration:
    """Test OpenRouter model wiring in call_single_llm."""

    def test_consensus_includes_openrouter_estimate(self) -> None:
        """Consensus result should carry the openrouter_estimate field."""
        est = LLMProbabilityEstimate(
            probability=0.72, confidence="medium", base_rate=0.5, reasoning="openrouter test"
        )
        result = calculate_consensus([("openrouter", est)])
        assert result.openrouter_estimate == 0.72
        assert result.claude_estimate is None
        assert abs(result.probability - 0.72) < 0.01

    def test_consensus_with_openrouter_and_claude(self) -> None:
        """OpenRouter and Claude estimates should both contribute to consensus."""
        e_or = LLMProbabilityEstimate(
            probability=0.60, confidence="medium", base_rate=0.5, reasoning="openrouter"
        )
        e_cl = LLMProbabilityEstimate(
            probability=0.80, confidence="medium", base_rate=0.5, reasoning="claude"
        )
        result = calculate_consensus([("openrouter", e_or), ("claude", e_cl)])
        assert result.openrouter_estimate == 0.60
        assert result.claude_estimate == 0.80
        assert 0.60 <= result.probability <= 0.80

    @pytest.mark.asyncio
    async def test_call_single_llm_openrouter_uses_openai_provider(
        self, trading_ctx
    ) -> None:
        """call_single_llm('openrouter', ...) should instantiate ChatOpenAI
        with OpenRouter base_url. We mock the actual LLM call."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from src.core.probability import call_single_llm

        mock_response = MagicMock()
        mock_response.content = (
            '{"probability": 0.65, "confidence": "medium", '
            '"base_rate": 0.5, "factors": [], "reasoning": "mock openrouter"}'
        )

        with patch(
            "langchain_openai.ChatOpenAI", autospec=True
        ) as MockChatOpenAI:
            mock_instance = MagicMock()
            mock_instance.ainvoke = AsyncMock(return_value=mock_response)
            MockChatOpenAI.return_value = mock_instance

            result = await call_single_llm("openrouter", "test prompt", trading_ctx)

            assert result is not None
            assert result.probability == 0.65
            assert result.confidence == "medium"

    @pytest.mark.asyncio
    async def test_call_single_llm_openrouter_sets_base_url(
        self, trading_ctx
    ) -> None:
        """Verify OpenRouter base_url and headers are set correctly."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from src.core.probability import call_single_llm

        mock_response = MagicMock()
        mock_response.content = (
            '{"probability": 0.55, "confidence": "low", '
            '"base_rate": 0.5, "factors": [], "reasoning": "test"}'
        )

        with patch(
            "langchain_openai.ChatOpenAI", autospec=True
        ) as MockChatOpenAI:
            mock_instance = MagicMock()
            mock_instance.ainvoke = AsyncMock(return_value=mock_response)
            MockChatOpenAI.return_value = mock_instance

            await call_single_llm("openrouter", "test prompt", trading_ctx)

            # Verify ChatOpenAI was called with correct OpenRouter config
            MockChatOpenAI.assert_called_once()
            call_kwargs = MockChatOpenAI.call_args
            assert call_kwargs.kwargs["base_url"] == "https://openrouter.ai/api/v1"
            assert "HTTP-Referer" in call_kwargs.kwargs["default_headers"]
            assert "X-Title" in call_kwargs.kwargs["default_headers"]

    @pytest.mark.asyncio
    async def test_call_single_llm_openrouter_failure_returns_none(
        self, trading_ctx
    ) -> None:
        """If OpenRouter call fails, should return None gracefully."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from src.core.probability import call_single_llm

        with patch(
            "langchain_openai.ChatOpenAI", autospec=True
        ) as MockChatOpenAI:
            mock_instance = MagicMock()
            mock_instance.ainvoke = AsyncMock(
                side_effect=Exception("OpenRouter rate limit exceeded")
            )
            MockChatOpenAI.return_value = mock_instance

            result = await call_single_llm("openrouter", "test prompt", trading_ctx)
            assert result is None


class TestCalibrationTracker:
    """Test Brier score calibration tracking."""

    @pytest.mark.asyncio
    async def test_record_resolution(self, repo) -> None:
        tracker = CalibrationTracker(repo)

        # Save an estimate
        await repo.save_probability_estimate({
            "market_id": "test_market",
            "model": "claude",
            "probability": 0.8,
            "confidence": "high",
            "reasoning": "test",
            "market_price_at_estimate": 0.5,
        })

        # Resolve as YES (outcome=1)
        scores = await tracker.record_resolution("test_market", 1)
        assert len(scores) == 1
        # Brier score for 0.8 estimate on outcome 1: (0.8 - 1)^2 = 0.04
        assert abs(scores[0] - 0.04) < 0.001

    @pytest.mark.asyncio
    async def test_rolling_brier_empty(self, repo) -> None:
        tracker = CalibrationTracker(repo)
        score = await tracker.get_rolling_brier()
        assert score == 0.25  # Naive baseline

    @pytest.mark.asyncio
    async def test_brier_score_persisted(self, repo) -> None:
        tracker = CalibrationTracker(repo)

        await repo.save_probability_estimate({
            "market_id": "m1",
            "model": "gpt",
            "probability": 0.6,
            "confidence": "medium",
            "reasoning": "test",
            "market_price_at_estimate": 0.5,
        })

        await tracker.record_resolution("m1", 0)
        # Brier for 0.6 on outcome 0: (0.6 - 0)^2 = 0.36
        scores = await repo.get_recent_brier_scores(10)
        assert len(scores) == 1
        assert abs(scores[0] - 0.36) < 0.001
