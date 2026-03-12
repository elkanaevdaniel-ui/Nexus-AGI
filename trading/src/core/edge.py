"""Edge detection — compares AI probabilities to market prices, accounts for fees."""

from __future__ import annotations

from decimal import Decimal

from src.data.schemas import ConsensusEstimate, EdgeResult

_ZERO = Decimal(0)
_ONE = Decimal(1)


def calculate_edge(
    estimate: ConsensusEstimate,
    market_price: float,
    fee_rate_bps: int = 200,
) -> EdgeResult:
    """Calculate fee-adjusted edge between estimated probability and market price.

    The edge is the difference between our estimated probability and
    the market price, minus the expected fee cost.

    Fee calculation: fee = baseRate * min(price, 1 - price) * size
    """
    mp = Decimal(str(market_price))
    base_rate = Decimal(fee_rate_bps) / Decimal(10_000)
    fee_pct = base_rate * min(mp, _ONE - mp)

    p_est = Decimal(str(estimate.probability))
    raw_edge = p_est - mp  # Positive = underpriced YES

    if raw_edge > _ZERO:
        direction = "BUY"
        edge_after_fees = raw_edge - fee_pct
    else:
        direction = "SELL"
        edge_after_fees = abs(raw_edge) - fee_pct

    return EdgeResult(
        magnitude=max(_ZERO, edge_after_fees),
        direction=direction,
        estimated_prob=p_est,
        market_price=mp,
        fee_pct=fee_pct,
        raw_edge=raw_edge,
    )
