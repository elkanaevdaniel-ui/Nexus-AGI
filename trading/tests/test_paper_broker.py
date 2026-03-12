"""Tests for paper broker fill simulation."""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.core.executor import PaperBroker
from src.data.schemas import OrderBookSummary


class TestPaperBrokerFillSimulation:
    """Test realistic fill simulation with orderbook depth."""

    def _orderbook(
        self,
        bids: list[tuple[str, str]] | None = None,
        asks: list[tuple[str, str]] | None = None,
    ) -> OrderBookSummary:
        return OrderBookSummary(
            bids=[{"price": p, "size": s} for p, s in (bids or [])],
            asks=[{"price": p, "size": s} for p, s in (asks or [])],
        )

    def test_full_fill_single_level(self) -> None:
        broker = PaperBroker()
        ob = self._orderbook(asks=[("0.50", "200")])
        fill = broker.simulate_fill("BUY", 0.50, 100, ob, 200)
        assert fill is not None
        assert fill.quantity == Decimal("100")
        assert fill.price == Decimal("0.50")

    def test_fill_across_multiple_levels(self) -> None:
        broker = PaperBroker()
        ob = self._orderbook(asks=[("0.50", "30"), ("0.51", "30"), ("0.52", "40")])
        fill = broker.simulate_fill("BUY", 0.55, 80, ob, 200)
        assert fill is not None
        assert fill.quantity == Decimal("80")
        # Weighted: (30*0.50 + 30*0.51 + 20*0.52) / 80
        expected = (15.0 + 15.3 + 10.4) / 80
        assert abs(float(fill.price) - expected) < 0.01

    def test_sell_side_fill(self) -> None:
        broker = PaperBroker()
        ob = self._orderbook(bids=[("0.55", "200")])
        fill = broker.simulate_fill("SELL", 0.50, 100, ob, 200)
        assert fill is not None
        assert fill.quantity == Decimal("100")
        assert fill.price == Decimal("0.55")

    def test_fee_proportional_to_min_price(self) -> None:
        # Price 0.80 -> min(0.80, 0.20) = 0.20
        fee = PaperBroker._calculate_fee(0.80, 100, 200)
        assert abs(float(fee) - 0.02 * 0.20 * 100) < 0.001

    def test_zero_liquidity(self) -> None:
        broker = PaperBroker()
        ob = self._orderbook(asks=[])
        fill = broker.simulate_fill("BUY", 0.50, 100, ob, 200)
        assert fill is None
