"""Tests for portfolio tracking, cost basis, and PnL."""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.core.portfolio import PortfolioTracker


class TestPortfolioTracker:
    """Test position management and PnL calculations."""

    @pytest.mark.asyncio
    async def test_open_position(self, trading_ctx) -> None:
        tracker = PortfolioTracker(initial_bankroll=1000.0)
        pos_id = await tracker.open_position(
            market_id="m1",
            token_id="t1",
            side="YES",
            quantity=100,
            price=0.50,
            fee=1.0,
            ctx=trading_ctx,
        )
        assert pos_id is not None
        expected = Decimal("1000") - (Decimal("100") * Decimal("0.50") + Decimal("1.0"))
        assert tracker.cash_balance == expected

    @pytest.mark.asyncio
    async def test_close_position_profit(self, trading_ctx) -> None:
        tracker = PortfolioTracker(initial_bankroll=1000.0)
        pos_id = await tracker.open_position(
            market_id="m1",
            token_id="t1",
            side="YES",
            quantity=100,
            price=0.50,
            fee=1.0,
            ctx=trading_ctx,
        )

        pnl = await tracker.close_position(
            position_id=pos_id,
            exit_price=0.70,
            quantity=100,
            fee=1.0,
            ctx=trading_ctx,
        )
        # PnL = (100 * 0.70 - 1.0) - (100 * 0.50) = 69 - 50 = 19.0
        assert abs(float(pnl) - 19.0) < 0.01

    @pytest.mark.asyncio
    async def test_close_position_loss(self, trading_ctx) -> None:
        tracker = PortfolioTracker(initial_bankroll=1000.0)
        pos_id = await tracker.open_position(
            market_id="m1",
            token_id="t1",
            side="YES",
            quantity=100,
            price=0.50,
            fee=1.0,
            ctx=trading_ctx,
        )

        pnl = await tracker.close_position(
            position_id=pos_id,
            exit_price=0.30,
            quantity=100,
            fee=1.0,
            ctx=trading_ctx,
        )
        # PnL = (100 * 0.30 - 1.0) - (100 * 0.50) = 29 - 50 = -21.0
        assert abs(float(pnl) - (-21.0)) < 0.01

    @pytest.mark.asyncio
    async def test_scale_in_updates_cost_basis(self, trading_ctx) -> None:
        tracker = PortfolioTracker(initial_bankroll=1000.0)

        # First buy: 100 @ 0.50
        pos_id = await tracker.open_position(
            market_id="m1", token_id="t1", side="YES",
            quantity=100, price=0.50, fee=0.0, ctx=trading_ctx,
        )
        # Scale in: 100 @ 0.60
        pos_id2 = await tracker.open_position(
            market_id="m1", token_id="t1", side="YES",
            quantity=100, price=0.60, fee=0.0, ctx=trading_ctx,
        )
        assert pos_id == pos_id2  # Same position

        pos = await trading_ctx.repo.get_position(pos_id)
        assert float(pos.quantity) == pytest.approx(200)
        # Avg = (100*0.50 + 100*0.60) / 200 = 0.55
        assert abs(float(pos.avg_entry_price) - 0.55) < 0.01

    @pytest.mark.asyncio
    async def test_resolve_yes_wins(self, trading_ctx) -> None:
        tracker = PortfolioTracker(initial_bankroll=1000.0)
        pos_id = await tracker.open_position(
            market_id="m1", token_id="t1", side="YES",
            quantity=100, price=0.50, fee=0.0, ctx=trading_ctx,
        )

        pnl = await tracker.resolve_position(pos_id, outcome=1, ctx=trading_ctx)
        # YES wins: proceeds = 100 * 1.0 = 100, cost = 50, pnl = 50
        assert abs(float(pnl) - 50.0) < 0.01

    @pytest.mark.asyncio
    async def test_resolve_yes_loses(self, trading_ctx) -> None:
        tracker = PortfolioTracker(initial_bankroll=1000.0)
        pos_id = await tracker.open_position(
            market_id="m1", token_id="t1", side="YES",
            quantity=100, price=0.50, fee=0.0, ctx=trading_ctx,
        )

        pnl = await tracker.resolve_position(pos_id, outcome=0, ctx=trading_ctx)
        # YES loses: proceeds = 100 * 0.0 = 0, cost = 50, pnl = -50
        assert abs(float(pnl) - (-50.0)) < 0.01

    @pytest.mark.asyncio
    async def test_get_summary(self, trading_ctx) -> None:
        tracker = PortfolioTracker(initial_bankroll=1000.0)
        summary = await tracker.get_summary(trading_ctx)
        assert float(summary.total_value) == pytest.approx(1000.0)
        assert float(summary.cash_balance) == pytest.approx(1000.0)
        assert summary.open_positions_count == 0

    @pytest.mark.asyncio
    async def test_save_snapshot(self, trading_ctx) -> None:
        tracker = PortfolioTracker(initial_bankroll=1000.0)
        await tracker.save_snapshot(trading_ctx)
        snapshot = await trading_ctx.repo.get_latest_portfolio_snapshot()
        assert snapshot is not None
        assert float(snapshot.total_value) == pytest.approx(1000.0)
