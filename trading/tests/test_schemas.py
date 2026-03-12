"""Tests for Pydantic schemas — validates all external data parsing."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.data.schemas import (
    ConsensusEstimate,
    DynamicConfigUpdate,
    EdgeResult,
    GammaMarket,
    HealthResponse,
    KellyResult,
    LLMProbabilityEstimate,
    OrderBookLevel,
    OrderBookSummary,
    RiskCheckResult,
    TradeDecision,
)


class TestGammaMarket:
    """Tests for Gamma API market schema."""

    def test_valid_market(self) -> None:
        """Should parse valid market data."""
        data = {
            "id": "0x123",
            "condition_id": "cond_1",
            "question": "Will BTC hit 100k?",
            "volume": 500000,
            "liquidity": 200000,
            "outcomes": ["Yes", "No"],
            "outcome_prices": ["0.65", "0.35"],
            "clob_token_ids": ["token_yes", "token_no"],
            "neg_risk": False,
            "active": True,
        }
        market = GammaMarket.model_validate(data)
        assert market.id == "0x123"
        assert market.volume == 500000

    def test_missing_optional_fields(self) -> None:
        """Should handle missing optional fields with defaults."""
        data = {"id": "0x456"}
        market = GammaMarket.model_validate(data)
        assert market.question == ""
        assert market.volume == 0.0
        assert market.active is True


class TestOrderBook:
    """Tests for order book schemas."""

    def test_parse_orderbook(self) -> None:
        """Should parse order book with levels."""
        data = {
            "market": "m1",
            "asset_id": "t1",
            "bids": [
                {"price": "0.45", "size": "100"},
                {"price": "0.44", "size": "200"},
            ],
            "asks": [
                {"price": "0.55", "size": "100"},
            ],
        }
        ob = OrderBookSummary.model_validate(data)
        assert len(ob.bids) == 2
        assert len(ob.asks) == 1
        assert ob.bids[0].price == "0.45"


class TestLLMProbabilityEstimate:
    """Tests for LLM probability output validation."""

    def test_valid_estimate(self) -> None:
        """Should accept valid probability estimate."""
        est = LLMProbabilityEstimate(
            probability=0.65,
            confidence="high",
            base_rate=0.50,
            factors=[
                {
                    "factor": "Strong polling data",
                    "direction": "up",
                    "magnitude": "large",
                }
            ],
            reasoning="Based on polling trends",
        )
        assert est.probability == 0.65

    def test_probability_clamped_low(self) -> None:
        """Should reject probability below 0.01."""
        with pytest.raises(ValidationError):
            LLMProbabilityEstimate(
                probability=0.0,
                confidence="low",
                base_rate=0.5,
            )

    def test_probability_clamped_high(self) -> None:
        """Should reject probability above 0.99."""
        with pytest.raises(ValidationError):
            LLMProbabilityEstimate(
                probability=1.0,
                confidence="high",
                base_rate=0.5,
            )

    def test_invalid_confidence(self) -> None:
        """Should reject invalid confidence levels."""
        with pytest.raises(ValidationError):
            LLMProbabilityEstimate(
                probability=0.5,
                confidence="very_high",  # Not valid
                base_rate=0.5,
            )


class TestTradeDecision:
    """Tests for trade decision schema."""

    def test_skip_decision(self) -> None:
        """Should create a SKIP decision."""
        decision = TradeDecision(
            action="SKIP",
            reason="Edge below threshold",
            market_id="m1",
        )
        assert decision.action == "SKIP"
        assert decision.size_usd == 0.0

    def test_buy_decision(self) -> None:
        """Should create a BUY decision with sizing."""
        decision = TradeDecision(
            action="BUY",
            market_id="m1",
            token_id="t1",
            size_usd=25.0,
            price=0.50,
        )
        assert decision.action == "BUY"
        assert decision.size_usd == 25.0

    def test_invalid_action(self) -> None:
        """Should reject invalid actions."""
        with pytest.raises(ValidationError):
            TradeDecision(action="HOLD")


class TestHealthResponse:
    """Tests for health check response."""

    def test_health_response(self) -> None:
        """Should create valid health response."""
        resp = HealthResponse(
            trading_mode="paper",
            trading_paused=False,
            uptime_seconds=3600.0,
        )
        assert resp.status == "ok"
        assert resp.trading_mode == "paper"
