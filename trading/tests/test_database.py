"""Tests for database models and repository."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
import pytest_asyncio

from src.data.models import (
    Alert,
    Base,
    CircuitBreakerEvent,
    LLMCall,
    Market,
    MarketResolution,
    Order,
    OrderEvent,
    Position,
    PortfolioSnapshot,
    ProbabilityEstimate,
    ReconciliationLog,
    Trade,
)
from src.data.repository import Repository


class TestModels:
    """Test that all 12 ORM models can be instantiated."""

    def test_all_tables_defined(self) -> None:
        """All 12 tables should be in the metadata."""
        table_names = set(Base.metadata.tables.keys())
        expected = {
            "markets",
            "positions",
            "orders",
            "trades",
            "probability_estimates",
            "portfolio_snapshots",
            "alerts",
            "market_resolutions",
            "reconciliation_log",
            "circuit_breaker_events",
            "order_events",
            "llm_calls",
        }
        assert expected.issubset(table_names), (
            f"Missing tables: {expected - table_names}"
        )


class TestRepository:
    """Tests for the data access layer."""

    @pytest.mark.asyncio
    async def test_upsert_and_get_market(self, repo: Repository) -> None:
        """Should insert and retrieve a market."""
        market_data = {
            "id": "market_1",
            "condition_id": "cond_1",
            "question": "Will it rain tomorrow?",
            "volume": 50000.0,
            "liquidity": 25000.0,
            "active": True,
        }
        market = await repo.upsert_market(market_data)
        assert market.id == "market_1"
        assert market.question == "Will it rain tomorrow?"

        fetched = await repo.get_market("market_1")
        assert fetched is not None
        assert fetched.volume == 50000.0

    @pytest.mark.asyncio
    async def test_upsert_market_updates(self, repo: Repository) -> None:
        """Upserting existing market should update, not duplicate."""
        await repo.upsert_market({
            "id": "market_update",
            "condition_id": "cond_u",
            "question": "Original question",
            "volume": 1000.0,
        })
        await repo.upsert_market({
            "id": "market_update",
            "condition_id": "cond_u",
            "question": "Updated question",
            "volume": 2000.0,
        })
        fetched = await repo.get_market("market_update")
        assert fetched is not None
        assert fetched.question == "Updated question"
        assert fetched.volume == 2000.0

    @pytest.mark.asyncio
    async def test_get_active_markets(self, repo: Repository) -> None:
        """Should return only active markets sorted by volume."""
        await repo.upsert_market({
            "id": "active_1",
            "condition_id": "c1",
            "question": "Q1",
            "volume": 100.0,
            "active": True,
        })
        await repo.upsert_market({
            "id": "inactive_1",
            "condition_id": "c2",
            "question": "Q2",
            "volume": 200.0,
            "active": False,
        })
        markets = await repo.get_active_markets()
        ids = [m.id for m in markets]
        assert "active_1" in ids
        assert "inactive_1" not in ids

    @pytest.mark.asyncio
    async def test_create_and_get_position(self, repo: Repository) -> None:
        """Should create and retrieve positions."""
        pos = await repo.create_position({
            "market_id": "m1",
            "token_id": "t1",
            "side": "YES",
            "quantity": 100.0,
            "cost_basis": 50.0,
            "avg_entry_price": 0.50,
            "current_price": 0.55,
            "unrealized_pnl": 5.0,
            "status": "open",
        })
        assert pos.id is not None
        assert pos.side == "YES"

        open_positions = await repo.get_open_positions()
        assert len(open_positions) >= 1

    @pytest.mark.asyncio
    async def test_update_position(self, repo: Repository) -> None:
        """Should update position fields."""
        pos = await repo.create_position({
            "id": "pos_update",
            "market_id": "m1",
            "token_id": "t1",
            "side": "YES",
            "quantity": 100.0,
            "cost_basis": 50.0,
            "avg_entry_price": 0.50,
            "current_price": 0.55,
            "unrealized_pnl": 5.0,
            "status": "open",
        })
        updated = await repo.update_position("pos_update", {
            "current_price": 0.60,
            "unrealized_pnl": 10.0,
        })
        assert updated is not None
        assert float(updated.current_price) == pytest.approx(0.60)

    @pytest.mark.asyncio
    async def test_create_order(self, repo: Repository) -> None:
        """Should create an order record."""
        order = await repo.create_order({
            "market_id": "m1",
            "token_id": "t1",
            "side": "BUY",
            "price": 0.50,
            "size": 100.0,
        })
        assert order.id is not None
        assert order.status == "pending"

    @pytest.mark.asyncio
    async def test_record_trade(self, repo: Repository) -> None:
        """Should record a trade fill."""
        trade = await repo.record_trade({
            "order_id": "ord_1",
            "market_id": "m1",
            "token_id": "t1",
            "side": "BUY",
            "price": 0.50,
            "size": 100.0,
            "fee": 1.0,
            "is_paper": True,
        })
        assert trade.id is not None
        assert float(trade.fee) == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_probability_estimates(self, repo: Repository) -> None:
        """Should save and retrieve probability estimates."""
        est = await repo.save_probability_estimate({
            "market_id": "m1",
            "model": "claude",
            "probability": 0.65,
            "confidence": "high",
            "reasoning": "Strong evidence",
            "market_price_at_estimate": 0.50,
        })
        assert est.id is not None

        estimates = await repo.get_estimates_for_market("m1")
        assert len(estimates) >= 1

    @pytest.mark.asyncio
    async def test_brier_score_tracking(self, repo: Repository) -> None:
        """Should save and retrieve Brier scores."""
        est = await repo.save_probability_estimate({
            "id": "est_brier",
            "market_id": "m_brier",
            "model": "claude",
            "probability": 0.70,
            "confidence": "high",
        })
        await repo.update_estimate_brier("est_brier", 0.09)  # (0.7-1)^2 = 0.09

        scores = await repo.get_recent_brier_scores(10)
        assert 0.09 in scores

    @pytest.mark.asyncio
    async def test_portfolio_snapshot(self, repo: Repository) -> None:
        """Should save and retrieve portfolio snapshots."""
        snap = await repo.save_portfolio_snapshot({
            "total_value": 1050.0,
            "cash_balance": 500.0,
            "positions_value": 550.0,
            "unrealized_pnl": 50.0,
            "realized_pnl": 0.0,
            "open_positions_count": 3,
        })
        assert snap.id is not None

        latest = await repo.get_latest_portfolio_snapshot()
        assert latest is not None
        assert float(latest.total_value) == pytest.approx(1050.0)

    @pytest.mark.asyncio
    async def test_reconciliation_log(self, repo: Repository) -> None:
        """Should log reconciliation events."""
        event = await repo.log_reconciliation_event({
            "reconciliation_type": "position",
            "market_id": "m1",
            "db_value": "100",
            "chain_value": "95",
            "discrepancy": "5 share difference",
        })
        assert event.id is not None

    @pytest.mark.asyncio
    async def test_circuit_breaker_event(self, repo: Repository) -> None:
        """Should log circuit breaker activations."""
        event = await repo.log_circuit_breaker({
            "breaker_type": "daily_loss",
            "trigger_value": 0.04,
            "threshold": 0.03,
            "action_taken": "paused_trading",
        })
        assert event.breaker_type == "daily_loss"

    @pytest.mark.asyncio
    async def test_llm_call_logging(self, repo: Repository) -> None:
        """Should log LLM API calls."""
        call = await repo.log_llm_call({
            "model": "claude-3-opus",
            "market_id": "m1",
            "input_tokens": 500,
            "output_tokens": 150,
            "cost_usd": 0.02,
            "latency_ms": 2500,
            "status": "success",
        })
        assert call.model == "claude-3-opus"
        assert float(call.cost_usd) == pytest.approx(0.02)
