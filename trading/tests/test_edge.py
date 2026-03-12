"""Tests for edge calculation module."""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.core.edge import calculate_edge
from src.data.schemas import ConsensusEstimate


class TestCalculateEdge:
    """Tests for fee-adjusted edge calculations."""

    def _estimate(self, prob: float, conf: str = "medium") -> ConsensusEstimate:
        return ConsensusEstimate(probability=prob, confidence=conf, reasoning="test")

    def test_positive_edge_buy(self) -> None:
        edge = calculate_edge(self._estimate(0.70), market_price=0.50, fee_rate_bps=200)
        assert edge.direction == "BUY"
        assert edge.magnitude > 0

    def test_negative_edge_sell(self) -> None:
        edge = calculate_edge(self._estimate(0.30), market_price=0.50, fee_rate_bps=200)
        assert edge.direction == "SELL"
        assert edge.magnitude > 0

    def test_no_edge_when_fees_consume_spread(self) -> None:
        edge = calculate_edge(self._estimate(0.51), market_price=0.50, fee_rate_bps=200)
        assert edge.magnitude == Decimal(0) or edge.magnitude < Decimal("0.01")

    def test_edge_at_extreme_price_low(self) -> None:
        edge = calculate_edge(self._estimate(0.50), market_price=0.05, fee_rate_bps=200)
        assert edge.direction == "BUY"
        assert edge.magnitude > 0

    def test_edge_at_extreme_price_high(self) -> None:
        edge = calculate_edge(self._estimate(0.50), market_price=0.95, fee_rate_bps=200)
        assert edge.direction == "SELL"
        assert edge.magnitude > 0

    def test_zero_fee_rate(self) -> None:
        edge = calculate_edge(self._estimate(0.60), market_price=0.50, fee_rate_bps=0)
        assert edge.fee_pct == Decimal(0)
        assert edge.magnitude == Decimal("0.1")

    def test_fee_pct_uses_min_of_price_and_complement(self) -> None:
        edge = calculate_edge(self._estimate(0.90), market_price=0.80, fee_rate_bps=200)
        assert edge.fee_pct == Decimal("0.02") * Decimal("0.2")  # 2% * min(0.8, 0.2)

    def test_raw_edge_preserved(self) -> None:
        edge = calculate_edge(self._estimate(0.70), market_price=0.50)
        assert edge.raw_edge == Decimal("0.2")

    def test_equal_price_and_estimate(self) -> None:
        edge = calculate_edge(self._estimate(0.50), market_price=0.50)
        assert edge.magnitude == Decimal(0)
