"""Tests for fee-adjusted Kelly criterion."""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.core.kelly import fee_adjusted_kelly


class TestFeeAdjustedKelly:
    """Test Kelly sizing with Polymarket fee structure."""

    def test_positive_edge_returns_nonzero_size(self) -> None:
        """Strong positive edge should produce a bet."""
        result = fee_adjusted_kelly(
            estimated_prob=0.70,
            market_price=0.50,
            fee_rate_bps=200,
            kelly_multiplier=0.25,
            bankroll=1000.0,
        )
        assert result.position_size_usd > 0
        assert result.fraction > 0
        assert result.expected_value > 0

    def test_no_edge_returns_zero(self) -> None:
        """No edge should produce zero bet."""
        result = fee_adjusted_kelly(
            estimated_prob=0.50,
            market_price=0.50,
            fee_rate_bps=200,
            kelly_multiplier=0.25,
            bankroll=1000.0,
        )
        assert result.position_size_usd == Decimal(0)
        assert result.fraction == Decimal(0)

    def test_negative_edge_returns_zero(self) -> None:
        """Negative edge should produce zero bet."""
        result = fee_adjusted_kelly(
            estimated_prob=0.40,
            market_price=0.50,
            fee_rate_bps=200,
            kelly_multiplier=0.25,
            bankroll=1000.0,
        )
        assert result.position_size_usd == Decimal(0)

    def test_fees_reduce_size(self) -> None:
        """Higher fees should reduce position size."""
        low_fee = fee_adjusted_kelly(
            estimated_prob=0.70,
            market_price=0.50,
            fee_rate_bps=100,
            bankroll=1000.0,
        )
        high_fee = fee_adjusted_kelly(
            estimated_prob=0.70,
            market_price=0.50,
            fee_rate_bps=400,
            bankroll=1000.0,
        )
        assert low_fee.position_size_usd >= high_fee.position_size_usd

    def test_position_cap(self) -> None:
        """Position should never exceed max_position_pct * bankroll."""
        result = fee_adjusted_kelly(
            estimated_prob=0.95,
            market_price=0.10,
            fee_rate_bps=200,
            kelly_multiplier=1.0,  # Full Kelly
            bankroll=1000.0,
            max_position_pct=0.05,
        )
        assert result.position_size_usd <= Decimal("50.00")  # 5% of 1000

    def test_quarter_kelly_reduces_fraction(self) -> None:
        """Quarter Kelly should be 25% of full Kelly."""
        full = fee_adjusted_kelly(
            estimated_prob=0.70,
            market_price=0.50,
            fee_rate_bps=200,
            kelly_multiplier=1.0,
            bankroll=10000.0,
            max_position_pct=1.0,
        )
        quarter = fee_adjusted_kelly(
            estimated_prob=0.70,
            market_price=0.50,
            fee_rate_bps=200,
            kelly_multiplier=0.25,
            bankroll=10000.0,
            max_position_pct=1.0,
        )
        assert abs(quarter.adjusted_fraction - full.adjusted_fraction * Decimal("0.25")) < Decimal("0.001")

    def test_extreme_probabilities_clamped(self) -> None:
        """Extreme inputs should still produce valid results."""
        result = fee_adjusted_kelly(
            estimated_prob=0.001,
            market_price=0.999,
            fee_rate_bps=200,
            bankroll=1000.0,
        )
        assert result.position_size_usd >= 0

    def test_edge_after_fees_in_result(self) -> None:
        """Edge after fees should be correctly computed."""
        result = fee_adjusted_kelly(
            estimated_prob=0.70,
            market_price=0.50,
            fee_rate_bps=200,
            bankroll=1000.0,
        )
        # edge = prob - market_price - fee_pct
        fee_pct = Decimal("0.02") * min(Decimal("0.50"), Decimal("0.50"))
        expected_edge = Decimal("0.70") - Decimal("0.50") - fee_pct
        assert abs(result.edge_after_fees - expected_edge) < Decimal("0.01")
