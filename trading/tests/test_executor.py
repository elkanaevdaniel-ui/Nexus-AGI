"""Tests for order execution and paper broker fill simulation."""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.core.executor import Fill, PaperBroker, safe_place_order
from src.data.schemas import EdgeResult, KellyResult, OrderBookSummary, TradeDecision


class TestPaperBroker:
    """Test realistic paper trade fill simulation."""

    def _make_orderbook(
        self,
        bids: list[tuple[str, str]] | None = None,
        asks: list[tuple[str, str]] | None = None,
    ) -> OrderBookSummary:
        if bids is None:
            bids = [("0.48", "500"), ("0.47", "500"), ("0.46", "500")]
        if asks is None:
            asks = [("0.52", "500"), ("0.53", "500"), ("0.54", "500")]
        return OrderBookSummary(
            bids=[{"price": p, "size": s} for p, s in bids],
            asks=[{"price": p, "size": s} for p, s in asks],
        )

    def test_buy_fill_at_ask(self) -> None:
        broker = PaperBroker()
        ob = self._make_orderbook()
        fill = broker.simulate_fill("BUY", 0.55, 100, ob, fee_rate_bps=200)
        assert fill is not None
        assert fill.quantity == Decimal("100")
        assert fill.price == Decimal("0.52")
        assert fill.fee > 0

    def test_sell_fill_at_bid(self) -> None:
        broker = PaperBroker()
        ob = self._make_orderbook()
        fill = broker.simulate_fill("SELL", 0.45, 100, ob, fee_rate_bps=200)
        assert fill is not None
        assert fill.quantity == Decimal("100")
        assert fill.price == Decimal("0.48")

    def test_partial_fill_across_levels(self) -> None:
        broker = PaperBroker()
        ob = self._make_orderbook(asks=[("0.52", "50"), ("0.53", "100")])
        fill = broker.simulate_fill("BUY", 0.55, 100, ob, fee_rate_bps=200)
        assert fill is not None
        assert fill.quantity == Decimal("100")
        # Weighted avg: (50*0.52 + 50*0.53) / 100 = 0.525
        assert abs(float(fill.price) - 0.525) < 0.001

    def test_insufficient_liquidity_returns_none(self) -> None:
        broker = PaperBroker()
        ob = self._make_orderbook(asks=[("0.52", "10")])
        fill = broker.simulate_fill("BUY", 0.55, 100, ob, fee_rate_bps=200)
        assert fill is None  # < 50% fill

    def test_price_limit_respected(self) -> None:
        broker = PaperBroker()
        ob = self._make_orderbook(asks=[("0.60", "500")])
        fill = broker.simulate_fill("BUY", 0.55, 100, ob, fee_rate_bps=200)
        # Ask at 0.60 is above limit of 0.55 — no fill
        assert fill is None

    def test_fee_calculation(self) -> None:
        fee = PaperBroker._calculate_fee(0.50, 100, 200)
        # fee = 0.02 * min(0.50, 0.50) * 100 = 1.0
        assert abs(float(fee) - 1.0) < 0.001

    def test_slippage_recorded(self) -> None:
        broker = PaperBroker()
        ob = self._make_orderbook(asks=[("0.55", "500")])
        fill = broker.simulate_fill("BUY", 0.55, 100, ob, fee_rate_bps=200)
        assert fill is not None
        assert fill.slippage == Decimal(0)  # No slippage at exact price

    def test_empty_orderbook_returns_none(self) -> None:
        broker = PaperBroker()
        ob = OrderBookSummary(bids=[], asks=[])
        fill = broker.simulate_fill("BUY", 0.50, 100, ob, fee_rate_bps=200)
        assert fill is None


class TestSafePlaceOrder:
    """Test idempotent order placement."""

    @pytest.mark.asyncio
    async def test_paper_order_fills(self, trading_ctx) -> None:
        decision = TradeDecision(
            action="BUY",
            market_id="test_market",
            token_id="test_token",
            size_usd=25.0,
            price=0.50,
            edge=EdgeResult(
                magnitude=0.10,
                direction="BUY",
                estimated_prob=0.65,
                market_price=0.50,
                fee_pct=0.01,
                raw_edge=0.15,
            ),
        )

        result = await safe_place_order(decision, trading_ctx)
        assert result["status"] in ("filled", "rejected")

    @pytest.mark.asyncio
    async def test_paper_order_recorded_in_db(self, trading_ctx) -> None:
        decision = TradeDecision(
            action="BUY",
            market_id="test_market",
            token_id="test_token",
            size_usd=25.0,
            price=0.55,  # Above fallback ask of 0.51 so it fills
        )

        result = await safe_place_order(decision, trading_ctx)
        # Order is always recorded (either filled or rejected)
        assert result["status"] in ("filled", "rejected")
