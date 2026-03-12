"""Tests for risk manager and circuit breakers."""

from __future__ import annotations

import pytest

from src.core.risk import RiskManager
from src.data.schemas import EdgeResult


class TestRiskManager:
    """Test risk checks and circuit breakers."""

    @pytest.mark.asyncio
    async def test_approves_valid_trade(self, trading_ctx) -> None:
        rm = RiskManager()
        rm.update_portfolio_value(1000.0)

        edge = EdgeResult(
            magnitude=0.10,
            direction="BUY",
            estimated_prob=0.65,
            market_price=0.50,
            fee_pct=0.01,
            raw_edge=0.15,
        )

        result = await rm.check(
            market_id="test",
            edge=edge,
            open_positions_count=2,
            portfolio_value=1000.0,
            ctx=trading_ctx,
        )
        assert result.approved is True

    @pytest.mark.asyncio
    async def test_rejects_below_edge_threshold(self, trading_ctx) -> None:
        rm = RiskManager()
        edge = EdgeResult(
            magnitude=0.01,
            direction="BUY",
            estimated_prob=0.51,
            market_price=0.50,
            fee_pct=0.01,
            raw_edge=0.01,
        )

        result = await rm.check(
            market_id="test",
            edge=edge,
            open_positions_count=0,
            portfolio_value=1000.0,
            ctx=trading_ctx,
        )
        assert result.approved is False
        assert "edge" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_rejects_max_positions(self, trading_ctx) -> None:
        rm = RiskManager()
        edge = EdgeResult(
            magnitude=0.10,
            direction="BUY",
            estimated_prob=0.65,
            market_price=0.50,
            fee_pct=0.01,
            raw_edge=0.15,
        )

        result = await rm.check(
            market_id="test",
            edge=edge,
            open_positions_count=20,  # Exceeds max (default is 10)
            portfolio_value=1000.0,
            ctx=trading_ctx,
        )
        assert result.approved is False
        assert "positions" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_rejects_when_paused(self, trading_ctx) -> None:
        rm = RiskManager()
        trading_ctx.trading_paused = True

        edge = EdgeResult(
            magnitude=0.10,
            direction="BUY",
            estimated_prob=0.65,
            market_price=0.50,
            fee_pct=0.01,
            raw_edge=0.15,
        )

        result = await rm.check(
            market_id="test",
            edge=edge,
            open_positions_count=0,
            portfolio_value=1000.0,
            ctx=trading_ctx,
        )
        assert result.approved is False
        trading_ctx.trading_paused = False

    @pytest.mark.asyncio
    async def test_daily_loss_circuit_breaker(self, trading_ctx) -> None:
        # Set explicit threshold for test (default is 1.0 = disabled for paper)
        trading_ctx.dynamic_config.max_daily_loss_pct = 0.25
        rm = RiskManager()
        rm.update_portfolio_value(1000.0)
        rm.record_pnl(-260.0)  # 26% daily loss > 25% threshold

        edge = EdgeResult(
            magnitude=0.10,
            direction="BUY",
            estimated_prob=0.65,
            market_price=0.50,
            fee_pct=0.01,
            raw_edge=0.15,
        )

        result = await rm.check(
            market_id="test",
            edge=edge,
            open_positions_count=0,
            portfolio_value=1000.0,
            ctx=trading_ctx,
        )
        assert result.approved is False
        assert rm.is_any_breaker_tripped
        assert "daily_loss" in rm.tripped_breakers

    @pytest.mark.asyncio
    async def test_drawdown_circuit_breaker(self, trading_ctx) -> None:
        # Set explicit threshold for test (default is 1.0 = disabled for paper)
        trading_ctx.dynamic_config.max_drawdown_pct = 0.30
        rm = RiskManager()
        rm._peak_value = 1000.0
        rm._current_value = 690.0  # 31% drawdown > 30% threshold

        edge = EdgeResult(
            magnitude=0.10,
            direction="BUY",
            estimated_prob=0.65,
            market_price=0.50,
            fee_pct=0.01,
            raw_edge=0.15,
        )

        result = await rm.check(
            market_id="test",
            edge=edge,
            open_positions_count=0,
            portfolio_value=690.0,
            ctx=trading_ctx,
        )
        assert result.approved is False
        assert "drawdown" in rm.tripped_breakers

    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks_all_trades(self, trading_ctx) -> None:
        rm = RiskManager()
        rm._circuit_breakers_tripped.add("test_breaker")

        edge = EdgeResult(
            magnitude=0.50,
            direction="BUY",
            estimated_prob=0.99,
            market_price=0.01,
            fee_pct=0.01,
            raw_edge=0.98,
        )

        result = await rm.check(
            market_id="test",
            edge=edge,
            open_positions_count=0,
            portfolio_value=1000.0,
            ctx=trading_ctx,
        )
        assert result.approved is False
        assert "circuit breaker" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_reset_breaker(self, trading_ctx) -> None:
        rm = RiskManager()
        rm._circuit_breakers_tripped.add("daily_loss")
        assert rm.is_any_breaker_tripped

        success = await rm.reset_breaker("daily_loss", trading_ctx)
        assert success is True
        assert not rm.is_any_breaker_tripped

    def test_reset_daily(self) -> None:
        rm = RiskManager()
        rm.record_pnl(-50.0)
        assert rm._daily_pnl == -50.0
        rm.reset_daily()
        assert rm._daily_pnl == 0.0
