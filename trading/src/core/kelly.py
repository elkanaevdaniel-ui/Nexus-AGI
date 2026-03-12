"""Fee-adjusted fractional Kelly criterion for position sizing."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from src.data.schemas import KellyResult

_ZERO = Decimal(0)
_ONE = Decimal(1)


def fee_adjusted_kelly(
    estimated_prob: float,
    market_price: float,
    fee_rate_bps: int = 200,
    kelly_multiplier: float = 0.25,
    bankroll: float = 1000.0,
    max_position_pct: float = 0.05,
) -> KellyResult:
    """Kelly criterion adjusted for Polymarket's fee structure.

    Fee calculation: fee = baseRate * min(price, 1 - price) * size
    This reduces the effective payout and MUST be included in sizing.

    Accepts float inputs for convenience but uses Decimal arithmetic
    internally to avoid floating-point accumulation errors.
    """
    # Convert inputs to Decimal
    p = Decimal(str(max(0.01, min(0.99, estimated_prob))))
    mp = Decimal(str(max(0.01, min(0.99, market_price))))
    km = Decimal(str(kelly_multiplier))
    bank = Decimal(str(bankroll))
    max_pct = Decimal(str(max_position_pct))

    # Fee calculation
    base_rate = Decimal(fee_rate_bps) / Decimal(10_000)
    fee_pct = base_rate * min(mp, _ONE - mp)

    # Net odds after fees:
    # You pay (cost + fee_on_entry) per token and receive 1.0 on win.
    # fee_on_entry = fee_pct * cost (fee is percentage of entry price)
    # So total cost = cost * (1 + fee_pct)
    # Net payout = 1.0 - total_cost, odds b = net_payout / total_cost
    cost = mp
    total_cost = cost * (_ONE + fee_pct)
    b = (_ONE - total_cost) / total_cost
    if b <= _ZERO:
        return KellyResult(
            fraction=_ZERO,
            adjusted_fraction=_ZERO,
            position_size_usd=_ZERO,
            edge_after_fees=_ZERO,
            expected_value=_ZERO,
        )

    # Kelly formula: f* = (b*p - q) / b
    q = _ONE - p
    raw_kelly = max(_ZERO, (b * p - q) / b)

    # Edge after fees (expected return minus total cost)
    edge_after_fees = p - total_cost

    # Apply fractional Kelly + position cap
    adjusted = raw_kelly * km
    max_bet = bank * max_pct
    position_size = min(adjusted * bank, max_bet)

    # Expected value per dollar bet (net of fees)
    ev = p * (_ONE - total_cost) - q * total_cost

    return KellyResult(
        fraction=raw_kelly.quantize(Decimal("0.000001"), ROUND_HALF_UP),
        adjusted_fraction=adjusted.quantize(Decimal("0.000001"), ROUND_HALF_UP),
        position_size_usd=position_size.quantize(Decimal("0.01"), ROUND_HALF_UP),
        edge_after_fees=edge_after_fees.quantize(Decimal("0.000001"), ROUND_HALF_UP),
        expected_value=ev.quantize(Decimal("0.000001"), ROUND_HALF_UP),
    )
