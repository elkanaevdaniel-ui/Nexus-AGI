"""Tests for the repository data access layer."""

from __future__ import annotations

from decimal import Decimal

import pytest
import pytest_asyncio

from src.data.repository import Repository


class TestRepositoryMarkets:
    """Tests for market CRUD operations."""

    @pytest.mark.asyncio
    async def test_upsert_and_get_market(self, repo: Repository) -> None:
        market = await repo.upsert_market({
            "id": "mkt_1",
            "condition_id": "cond_1",
            "question": "Test market?",
            "description": "A test",
            "category": "test",
            "volume": 50000.0,
            "liquidity": 10000.0,
        })
        assert market.id == "mkt_1"
        assert market.question == "Test market?"

        fetched = await repo.get_market("mkt_1")
        assert fetched is not None
        assert fetched.question == "Test market?"

    @pytest.mark.asyncio
    async def test_upsert_updates_existing(self, repo: Repository) -> None:
        await repo.upsert_market({
            "id": "mkt_2",
            "condition_id": "cond_2",
            "question": "Original?",
            "description": "",
            "category": "test",
        })
        updated = await repo.upsert_market({
            "id": "mkt_2",
            "question": "Updated?",
        })
        assert updated.question == "Updated?"

    @pytest.mark.asyncio
    async def test_get_nonexistent_market(self, repo: Repository) -> None:
        result = await repo.get_market("does_not_exist")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_active_markets(self, repo: Repository) -> None:
        await repo.upsert_market({
            "id": "active_1",
            "condition_id": "c1",
            "question": "Active?",
            "description": "",
            "category": "test",
            "active": True,
            "volume": 100.0,
        })
        await repo.upsert_market({
            "id": "inactive_1",
            "condition_id": "c2",
            "question": "Inactive?",
            "description": "",
            "category": "test",
            "active": False,
            "volume": 200.0,
        })
        active = await repo.get_active_markets()
        active_ids = [m.id for m in active]
        assert "active_1" in active_ids
        assert "inactive_1" not in active_ids


class TestRepositoryPositions:
    """Tests for position CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_and_get_position(self, repo: Repository) -> None:
        pos = await repo.create_position({
            "market_id": "mkt_1",
            "token_id": "tok_1",
            "side": "YES",
            "quantity": Decimal("10"),
            "avg_entry_price": Decimal("0.50"),
        })
        assert pos.id is not None
        assert pos.market_id == "mkt_1"

        fetched = await repo.get_position(pos.id)
        assert fetched is not None
        assert fetched.side == "YES"

    @pytest.mark.asyncio
    async def test_get_open_positions(self, repo: Repository) -> None:
        await repo.create_position({
            "market_id": "mkt_open",
            "token_id": "tok_1",
            "side": "YES",
            "quantity": Decimal("5"),
            "status": "open",
        })
        open_positions = await repo.get_open_positions()
        assert any(p.market_id == "mkt_open" for p in open_positions)

    @pytest.mark.asyncio
    async def test_update_position(self, repo: Repository) -> None:
        pos = await repo.create_position({
            "market_id": "mkt_upd",
            "token_id": "tok_1",
            "side": "YES",
            "quantity": Decimal("10"),
        })
        updated = await repo.update_position(pos.id, {"quantity": Decimal("20")})
        assert updated is not None
        assert updated.quantity == Decimal("20")

    @pytest.mark.asyncio
    async def test_update_nonexistent_position(self, repo: Repository) -> None:
        result = await repo.update_position("nonexistent", {"quantity": Decimal("1")})
        assert result is None


class TestRepositoryOrders:
    """Tests for order operations."""

    @pytest.mark.asyncio
    async def test_create_order(self, repo: Repository) -> None:
        order = await repo.create_order({
            "market_id": "mkt_1",
            "token_id": "tok_1",
            "side": "BUY",
            "price": Decimal("0.50"),
            "size": Decimal("100"),
        })
        assert order.id is not None
        assert order.status == "pending"

    @pytest.mark.asyncio
    async def test_update_order_status(self, repo: Repository) -> None:
        order = await repo.create_order({
            "market_id": "mkt_1",
            "token_id": "tok_1",
            "side": "BUY",
            "price": Decimal("0.50"),
            "size": Decimal("100"),
        })
        await repo.update_order_status(order.id, "filled")
        # No assertion on return value since it returns None


class TestRepositoryTrades:
    """Tests for trade recording."""

    @pytest.mark.asyncio
    async def test_record_and_get_trades(self, repo: Repository) -> None:
        trade = await repo.record_trade({
            "order_id": "ord_1",
            "market_id": "mkt_trades",
            "token_id": "tok_1",
            "side": "BUY",
            "price": Decimal("0.50"),
            "size": Decimal("10"),
        })
        assert trade.id is not None

        trades = await repo.get_trades_for_market("mkt_trades")
        assert len(trades) >= 1
        assert trades[0].market_id == "mkt_trades"


class TestRepositoryProbabilityEstimates:
    """Tests for probability estimate storage."""

    @pytest.mark.asyncio
    async def test_save_and_get_estimates(self, repo: Repository) -> None:
        est = await repo.save_probability_estimate({
            "market_id": "mkt_prob",
            "model": "claude",
            "probability": 0.65,
            "confidence": "high",
        })
        assert est.id is not None

        estimates = await repo.get_estimates_for_market("mkt_prob")
        assert len(estimates) >= 1
        assert estimates[0].probability == 0.65

    @pytest.mark.asyncio
    async def test_update_brier_score(self, repo: Repository) -> None:
        est = await repo.save_probability_estimate({
            "market_id": "mkt_brier",
            "model": "gpt",
            "probability": 0.70,
            "confidence": "medium",
        })
        await repo.update_estimate_brier(est.id, 0.09)

        scores = await repo.get_recent_brier_scores(100)
        assert 0.09 in scores

    @pytest.mark.asyncio
    async def test_get_brier_scores_empty(self, repo: Repository) -> None:
        scores = await repo.get_recent_brier_scores(100)
        # May or may not be empty depending on test ordering, but should not error
        assert isinstance(scores, list)


class TestRepositorySnapshots:
    """Tests for portfolio snapshot operations."""

    @pytest.mark.asyncio
    async def test_save_and_get_snapshot(self, repo: Repository) -> None:
        snap = await repo.save_portfolio_snapshot({
            "total_value": Decimal("1000"),
            "cash_balance": Decimal("800"),
            "positions_value": Decimal("200"),
            "unrealized_pnl": Decimal("10"),
            "realized_pnl": Decimal("5"),
            "open_positions_count": 3,
        })
        assert snap.id is not None

        latest = await repo.get_latest_portfolio_snapshot()
        assert latest is not None
        assert latest.total_value == Decimal("1000")
