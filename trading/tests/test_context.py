"""Tests for TradingContext."""

from __future__ import annotations

import pytest

from src.context import TradingContext


class TestTradingContext:
    """Tests for the dependency injection context."""

    def test_is_paper_mode(self, trading_ctx: TradingContext) -> None:
        """Should detect paper trading mode."""
        assert trading_ctx.is_paper is True
        assert trading_ctx.is_live is False

    def test_uptime_positive(self, trading_ctx: TradingContext) -> None:
        """Uptime should be positive after creation."""
        assert trading_ctx.uptime_seconds >= 0

    def test_clob_client_available(self, trading_ctx: TradingContext) -> None:
        """Mock CLOB client should be available."""
        assert trading_ctx.clob is not None

    def test_monitored_tokens_empty(self, trading_ctx: TradingContext) -> None:
        """Should start with no monitored tokens."""
        assert trading_ctx.monitored_token_ids == []
