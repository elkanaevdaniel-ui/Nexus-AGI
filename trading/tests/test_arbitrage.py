"""Tests for arbitrage detection."""

from __future__ import annotations

import pytest

from src.core.arbitrage import detect_arbitrage


class TestArbitrageDetection:
    """Test Dutch book arbitrage detection."""

    def test_dutch_book_detected(self) -> None:
        """YES + NO < 1.0 should detect a Dutch book."""
        arb = detect_arbitrage(
            yes_price=0.40,
            no_price=0.45,
            market_id="test",
            fee_rate_bps=200,
        )
        assert arb is not None
        assert abs(arb.combined_price - 0.85) < 1e-10
        assert abs(arb.profit_before_fees - 0.15) < 1e-10
        assert arb.profit_after_fees > 0

    def test_no_arb_when_prices_sum_to_one(self) -> None:
        arb = detect_arbitrage(
            yes_price=0.50,
            no_price=0.50,
            fee_rate_bps=200,
        )
        assert arb is None

    def test_no_arb_when_sum_exceeds_one(self) -> None:
        arb = detect_arbitrage(
            yes_price=0.55,
            no_price=0.55,
            fee_rate_bps=200,
        )
        assert arb is None

    def test_fees_can_eliminate_arb(self) -> None:
        """Tiny Dutch book may not be profitable after fees."""
        arb = detect_arbitrage(
            yes_price=0.49,
            no_price=0.49,
            market_id="test",
            fee_rate_bps=500,  # High fees
        )
        # Combined = 0.98, profit_before = 0.02
        # Fees will likely exceed the 2% gap
        assert arb is None

    def test_large_dutch_book(self) -> None:
        arb = detect_arbitrage(
            yes_price=0.30,
            no_price=0.40,
            market_id="test",
            fee_rate_bps=200,
        )
        assert arb is not None
        assert arb.profit_after_fees > 0.10
