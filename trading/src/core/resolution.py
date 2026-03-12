"""Market resolution handler and settlement."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from src.context import TradingContext
    from src.core.portfolio import PortfolioTracker
    from src.core.probability import CalibrationTracker


async def check_resolutions(
    ctx: TradingContext,
    portfolio: PortfolioTracker,
    calibration: CalibrationTracker,
) -> list[dict]:
    """Check for newly resolved markets and settle positions.

    Returns list of settlement results.
    """
    settlements: list[dict] = []

    # Get markets from Gamma that have resolved
    try:
        resolved_markets = await ctx.gamma.get_markets(
            limit=50, active=False, closed=True
        )
    except Exception as e:
        logger.warning(f"Failed to fetch resolved markets: {e}")
        return settlements

    open_positions = await ctx.repo.get_open_positions()
    open_market_ids = {p.market_id for p in open_positions}

    for market in resolved_markets:
        if market.id not in open_market_ids:
            continue

        # Determine outcome from prices (resolved markets show 1.0/0.0)
        outcome = _determine_outcome(market.outcome_prices)
        if outcome is None:
            continue

        # Check if we already recorded this resolution
        existing = await ctx.repo.get_market(market.id)
        if existing and not existing.active:
            continue

        # Record resolution
        await ctx.repo.record_resolution({
            "market_id": market.id,
            "outcome": outcome,
            "resolved_at": datetime.now(timezone.utc),
        })

        # Update market as inactive
        await ctx.repo.upsert_market({"id": market.id, "active": False})

        # Settle all positions in this market
        market_positions = [p for p in open_positions if p.market_id == market.id]
        for pos in market_positions:
            pnl = await portfolio.resolve_position(pos.id, outcome, ctx)
            settlements.append({
                "market_id": market.id,
                "position_id": pos.id,
                "outcome": outcome,
                "pnl": pnl,
            })

            logger.info(
                f"Settled position {pos.id} in market {market.id}: "
                f"outcome={'YES' if outcome == 1 else 'NO'}, pnl={pnl:+.4f}"
            )

        # Score calibration
        await calibration.record_resolution(market.id, outcome)

    return settlements


def _determine_outcome(outcome_prices: list[str]) -> int | None:
    """Determine the outcome from resolved market prices.

    Resolved markets typically show 1.0/0.0 for YES/NO prices.
    Returns 1 for YES, 0 for NO, None if unclear.
    """
    if not outcome_prices or len(outcome_prices) < 2:
        return None

    try:
        yes_price = float(outcome_prices[0])
        no_price = float(outcome_prices[1])
    except (ValueError, IndexError):
        return None

    if yes_price >= 0.95:
        return 1
    if no_price >= 0.95:
        return 0
    return None
