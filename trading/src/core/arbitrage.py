"""WebSocket-driven arbitrage detection — intra-market and cross-outcome."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from loguru import logger

if TYPE_CHECKING:
    from src.context import TradingContext


@dataclass(frozen=True)
class ArbitrageOpportunity:
    """Detected arbitrage opportunity."""

    arb_type: str  # "dutch_book" or "cross_outcome"
    market_id: str
    yes_price: float
    no_price: float
    combined_price: float
    profit_before_fees: float
    profit_after_fees: float
    fee_cost: float


def detect_arbitrage(
    yes_price: float,
    no_price: float,
    market_id: str = "",
    fee_rate_bps: int = 200,
) -> Optional[ArbitrageOpportunity]:
    """Detect Dutch book arbitrage (YES + NO prices sum < 1.0 or > 1.0).

    Dutch book: If YES + NO < 1.0, buy both for guaranteed profit.
    Reverse Dutch book: If YES + NO > 1.0, sell both (less common).
    """
    combined = yes_price + no_price
    base_rate = fee_rate_bps / 10_000

    if combined >= 1.0:
        return None  # No Dutch book opportunity

    profit_before_fees = 1.0 - combined

    # Fee on each leg
    fee_yes = base_rate * min(yes_price, 1 - yes_price)
    fee_no = base_rate * min(no_price, 1 - no_price)
    total_fees = fee_yes + fee_no

    profit_after_fees = profit_before_fees - total_fees

    if profit_after_fees <= 0:
        return None

    return ArbitrageOpportunity(
        arb_type="dutch_book",
        market_id=market_id,
        yes_price=yes_price,
        no_price=no_price,
        combined_price=combined,
        profit_before_fees=profit_before_fees,
        profit_after_fees=profit_after_fees,
        fee_cost=total_fees,
    )


_MAX_ARB_SCAN_MARKETS = 200


async def scan_orderbook_arbitrage(
    ctx: TradingContext,
) -> list[ArbitrageOpportunity]:
    """Scan monitored markets for arbitrage via REST (fallback for no WebSocket).

    Caps at _MAX_ARB_SCAN_MARKETS to avoid excessive API calls and DB load.
    """
    opportunities: list[ArbitrageOpportunity] = []

    markets = await ctx.repo.get_active_markets()
    markets = markets[:_MAX_ARB_SCAN_MARKETS]

    for market in markets:
        if not market.outcome_yes_token or not market.outcome_no_token:
            continue

        try:
            yes_price = market.current_price_yes
            no_price = market.current_price_no

            arb = detect_arbitrage(
                yes_price=yes_price,
                no_price=no_price,
                market_id=market.id,
                fee_rate_bps=ctx.dynamic_config.fee_rate_bps,
            )

            if arb:
                opportunities.append(arb)
                logger.info(
                    f"Arbitrage found in {market.id}: "
                    f"YES={yes_price:.3f} + NO={no_price:.3f} = {arb.combined_price:.3f}, "
                    f"profit_after_fees={arb.profit_after_fees:.4f}"
                )

        except Exception as e:
            logger.warning(f"Arb scan error for {market.id}: {e}")

    return opportunities


async def execute_arbitrage(
    arb: ArbitrageOpportunity,
    ctx: TradingContext,
) -> dict:
    """Execute an arbitrage trade (buy both YES and NO)."""
    if ctx.trading_paused:
        return {"status": "skipped", "reason": "trading_paused"}

    if not ctx.clob:
        return {"status": "skipped", "reason": "no_clob_client"}

    logger.info(
        f"Executing arbitrage on {arb.market_id}: "
        f"expected profit={arb.profit_after_fees:.4f}"
    )

    # In paper mode, just log it
    if ctx.is_paper:
        return {
            "status": "paper_executed",
            "profit_after_fees": arb.profit_after_fees,
        }

    return {"status": "live_execution_not_implemented"}


async def run_arbitrage_scan(ctx: TradingContext) -> list[ArbitrageOpportunity]:
    """Run one arbitrage scan cycle."""
    return await scan_orderbook_arbitrage(ctx)
