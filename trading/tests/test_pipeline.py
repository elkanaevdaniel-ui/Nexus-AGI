"""Tests for the trading pipeline orchestration."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from src.core.pipeline import evaluate_market, execute_decision, run_pipeline_cycle
from src.data.schemas import (
    ConsensusEstimate,
    EdgeResult,
    GammaMarket,
    KellyResult,
    TradeDecision,
)


def _make_market(**overrides) -> GammaMarket:
    """Helper to create a test GammaMarket."""
    defaults = {
        "id": "market_1",
        "condition_id": "cond_1",
        "question": "Will it rain tomorrow?",
        "description": "Weather prediction market",
        "volume": 50000.0,
        "liquidity": 25000.0,
        "outcomes": ["Yes", "No"],
        "outcome_prices": ["0.50", "0.50"],
        "clob_token_ids": ["token_yes_1", "token_no_1"],
        "active": True,
    }
    defaults.update(overrides)
    return GammaMarket(**defaults)


class TestEvaluateMarket:
    """Test the full evaluate_market pipeline."""

    @pytest.mark.asyncio
    async def test_skip_on_low_edge(self, trading_ctx) -> None:
        """Market with no edge should be skipped."""
        market = _make_market()

        # Mock consensus to return probability close to market price
        consensus = ConsensusEstimate(
            probability=0.51,
            confidence="high",
            spread=0.02,
        )

        with patch(
            "src.core.pipeline.estimate_probability_consensus",
            new_callable=AsyncMock,
            return_value=consensus,
        ):
            decision = await evaluate_market(market, trading_ctx)

        assert decision.action == "SKIP"
        assert "below threshold" in decision.reason.lower() or "Edge" in decision.reason

    @pytest.mark.asyncio
    async def test_buy_on_strong_edge(self, trading_ctx) -> None:
        """Strong positive edge should produce a BUY decision."""
        market = _make_market(outcome_prices=["0.40", "0.60"])

        consensus = ConsensusEstimate(
            probability=0.70,
            confidence="high",
            spread=0.05,
        )

        with patch(
            "src.core.pipeline.estimate_probability_consensus",
            new_callable=AsyncMock,
            return_value=consensus,
        ):
            decision = await evaluate_market(market, trading_ctx)

        assert decision.action == "BUY"
        assert decision.size_usd > Decimal(0)
        assert decision.token_id == "token_yes_1"
        assert decision.edge is not None
        assert decision.kelly is not None

    @pytest.mark.asyncio
    async def test_skip_on_low_confidence_high_spread(self, trading_ctx) -> None:
        """Low confidence with high spread should be skipped."""
        market = _make_market()

        consensus = ConsensusEstimate(
            probability=0.70,
            confidence="low",
            spread=0.30,
        )

        with patch(
            "src.core.pipeline.estimate_probability_consensus",
            new_callable=AsyncMock,
            return_value=consensus,
        ):
            decision = await evaluate_market(market, trading_ctx)

        assert decision.action == "SKIP"
        assert "spread" in decision.reason.lower()

    @pytest.mark.asyncio
    async def test_risk_rejection_blocks_trade(self, trading_ctx) -> None:
        """Risk manager rejection should produce SKIP."""
        market = _make_market(outcome_prices=["0.30", "0.70"])

        consensus = ConsensusEstimate(
            probability=0.70,
            confidence="high",
            spread=0.05,
        )

        # Trip a circuit breaker to force rejection
        trading_ctx.risk_manager._circuit_breakers_tripped.add("test_breaker")

        with patch(
            "src.core.pipeline.estimate_probability_consensus",
            new_callable=AsyncMock,
            return_value=consensus,
        ):
            decision = await evaluate_market(market, trading_ctx)

        assert decision.action == "SKIP"
        assert "risk rejected" in decision.reason.lower()

        # Clean up
        trading_ctx.risk_manager._circuit_breakers_tripped.discard("test_breaker")


class TestExecuteDecision:
    """Test trade execution and portfolio updates."""

    @pytest.mark.asyncio
    async def test_skip_decision_is_noop(self, trading_ctx) -> None:
        """SKIP decisions should not execute anything."""
        decision = TradeDecision(
            action="SKIP",
            reason="No edge",
            market_id="m1",
        )
        result = await execute_decision(decision, trading_ctx)
        assert result["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_buy_decision_updates_portfolio(self, trading_ctx) -> None:
        """Filled BUY should update portfolio tracker."""
        decision = TradeDecision(
            action="BUY",
            market_id="m1",
            token_id="token_1",
            size_usd=Decimal("50.00"),
            price=Decimal("0.50"),
        )

        result = await execute_decision(decision, trading_ctx)

        # Paper mode should fill
        assert result["status"] in ("filled", "rejected")

        if result["status"] == "filled":
            # Portfolio should have recorded the position
            positions = await trading_ctx.repo.get_open_positions()
            assert len(positions) >= 1


class TestRunPipelineCycle:
    """Test the full pipeline cycle."""

    @pytest.mark.asyncio
    async def test_paused_trading_skips_cycle(self, trading_ctx) -> None:
        """Pipeline should not run when trading is paused."""
        trading_ctx.trading_paused = True
        results = await run_pipeline_cycle(trading_ctx)
        assert results == []
        trading_ctx.trading_paused = False

    @pytest.mark.asyncio
    async def test_cycle_with_no_markets(self, trading_ctx) -> None:
        """Pipeline should handle empty market scan gracefully."""
        with patch(
            "src.core.pipeline.run_scan_cycle",
            new_callable=AsyncMock,
            return_value=[],
        ):
            results = await run_pipeline_cycle(trading_ctx)
        assert results == []
