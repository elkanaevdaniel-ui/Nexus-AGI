"""Tests for signal collectors and aggregator."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from src.signals.aggregator import (
    SignalAggregator,
    extract_keywords,
    format_signals_for_prompt,
)
from src.signals.types import MarketSignals, Signal


class TestExtractKeywords:
    """Test keyword extraction from market questions."""

    def test_removes_stop_words(self) -> None:
        keywords = extract_keywords("Will the price of Bitcoin reach $100k?")
        assert "will" not in [k.lower() for k in keywords]
        assert "the" not in [k.lower() for k in keywords]
        assert "of" not in [k.lower() for k in keywords]

    def test_keeps_meaningful_words(self) -> None:
        keywords = extract_keywords("Will Bitcoin reach $100k by December 2026?")
        lower = [k.lower() for k in keywords]
        assert "bitcoin" in lower
        assert "reach" in lower
        assert "december" in lower

    def test_deduplicates(self) -> None:
        keywords = extract_keywords("Bitcoin bitcoin BITCOIN price")
        lower = [k.lower() for k in keywords]
        assert lower.count("bitcoin") == 1

    def test_caps_at_10(self) -> None:
        long_q = " ".join(f"word{i}" for i in range(20))
        keywords = extract_keywords(long_q)
        assert len(keywords) <= 10

    def test_empty_question(self) -> None:
        assert extract_keywords("") == []

    def test_political_question(self) -> None:
        keywords = extract_keywords(
            "Will Trump win the 2026 presidential election?"
        )
        lower = [k.lower() for k in keywords]
        assert "trump" in lower
        assert "presidential" in lower
        assert "election" in lower


class TestFormatSignalsForPrompt:
    """Test signal formatting for LLM context injection."""

    def test_empty_signals(self) -> None:
        ms = MarketSignals(market_id="m1", question="test?")
        result = format_signals_for_prompt(ms)
        assert "No external signals" in result

    def test_formats_with_signals(self) -> None:
        ms = MarketSignals(
            market_id="m1",
            question="test?",
            signals=[
                Signal(
                    source="search",
                    title="Test result",
                    body="Some snippet",
                    published_at=datetime.now(timezone.utc),
                    relevance=0.9,
                ),
                Signal(
                    source="reddit",
                    title="Reddit post",
                    body="Discussion content",
                    published_at=datetime.now(timezone.utc),
                    relevance=0.5,
                ),
            ],
            signal_count=2,
            overall_sentiment=0.3,
        )
        result = format_signals_for_prompt(ms)
        assert "Google Search" in result
        assert "Reddit" in result
        assert "Test result" in result
        assert "sentiment" in result

    def test_groups_by_source(self) -> None:
        signals = [
            Signal(
                source="twitter",
                title=f"Tweet {i}",
                published_at=datetime.now(timezone.utc),
                relevance=0.5,
            )
            for i in range(3)
        ]
        ms = MarketSignals(
            market_id="m1",
            question="test?",
            signals=signals,
            signal_count=3,
        )
        result = format_signals_for_prompt(ms)
        assert "Twitter/X" in result


class TestSignalAggregator:
    """Test the unified signal aggregator."""

    @pytest.mark.asyncio
    async def test_gather_with_no_keys(self, trading_ctx) -> None:
        """With no API keys configured, should return empty signals gracefully."""
        agg = SignalAggregator()
        result = await agg.gather("m1", "Will Bitcoin hit $100k?", trading_ctx)

        assert isinstance(result, MarketSignals)
        assert result.market_id == "m1"
        assert result.signal_count == 0

    @pytest.mark.asyncio
    async def test_gather_deduplicates_urls(self, trading_ctx) -> None:
        """Signals with same URL should be deduplicated."""
        dup_signal = Signal(
            source="search",
            title="Duplicate",
            url="https://example.com/article",
            published_at=datetime.now(timezone.utc),
            relevance=0.5,
        )

        agg = SignalAggregator()

        # Mock all collectors to return duplicates
        with (
            patch.object(agg._search, "collect", new_callable=AsyncMock, return_value=[dup_signal]),
            patch.object(agg._search, "collect_news", new_callable=AsyncMock, return_value=[dup_signal]),
            patch.object(agg._reddit, "collect", new_callable=AsyncMock, return_value=[]),
            patch.object(agg._twitter, "collect", new_callable=AsyncMock, return_value=[]),
            patch.object(agg._trends, "collect", new_callable=AsyncMock, return_value=[]),
        ):
            result = await agg.gather("m1", "test?", trading_ctx)

        assert result.signal_count == 1  # Deduped

    @pytest.mark.asyncio
    async def test_gather_handles_collector_errors(self, trading_ctx) -> None:
        """If a collector raises, others should still work."""
        good_signal = Signal(
            source="reddit",
            title="Good signal",
            published_at=datetime.now(timezone.utc),
            relevance=0.7,
        )

        agg = SignalAggregator()

        with (
            patch.object(agg._search, "collect", new_callable=AsyncMock, side_effect=RuntimeError("boom")),
            patch.object(agg._search, "collect_news", new_callable=AsyncMock, side_effect=RuntimeError("boom")),
            patch.object(agg._reddit, "collect", new_callable=AsyncMock, return_value=[good_signal]),
            patch.object(agg._twitter, "collect", new_callable=AsyncMock, return_value=[]),
            patch.object(agg._trends, "collect", new_callable=AsyncMock, return_value=[]),
        ):
            result = await agg.gather("m1", "test?", trading_ctx)

        assert result.signal_count == 1
        assert result.signals[0].title == "Good signal"

    @pytest.mark.asyncio
    async def test_sentiment_aggregation(self, trading_ctx) -> None:
        """Overall sentiment should be weighted by relevance."""
        signals = [
            Signal(
                source="reddit",
                title="Bullish post",
                published_at=datetime.now(timezone.utc),
                sentiment=0.8,
                relevance=1.0,
            ),
            Signal(
                source="twitter",
                title="Bearish tweet",
                published_at=datetime.now(timezone.utc),
                sentiment=-0.4,
                relevance=0.5,
            ),
        ]

        agg = SignalAggregator()

        with (
            patch.object(agg._search, "collect", new_callable=AsyncMock, return_value=[]),
            patch.object(agg._search, "collect_news", new_callable=AsyncMock, return_value=[]),
            patch.object(agg._reddit, "collect", new_callable=AsyncMock, return_value=[signals[0]]),
            patch.object(agg._twitter, "collect", new_callable=AsyncMock, return_value=[signals[1]]),
            patch.object(agg._trends, "collect", new_callable=AsyncMock, return_value=[]),
        ):
            result = await agg.gather("m1", "test?", trading_ctx)

        # Weighted: (0.8*1.0 + -0.4*0.5) / (1.0+0.5) = 0.6/1.5 = 0.4
        assert result.overall_sentiment > 0  # Net bullish
        assert result.bullish_count == 1
        assert result.bearish_count == 1
