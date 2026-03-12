"""Market scanner — discovers and filters tradable markets from Gamma API."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

from loguru import logger

from src.data.schemas import GammaMarket
from src.utils.metrics import MARKETS_SCANNED, MARKETS_WITH_EDGE

if TYPE_CHECKING:
    from src.context import TradingContext


async def fetch_candidate_markets(ctx: TradingContext) -> list[GammaMarket]:
    """Tier 0: Fetch and filter markets by basic criteria (volume, liquidity, active)."""
    all_markets: list[GammaMarket] = []
    offset = 0
    batch_size = 100

    while True:
        batch = await ctx.gamma.get_markets(
            limit=batch_size,
            offset=offset,
            active=True,
            closed=False,
            order="volume",
            ascending=False,
        )
        if not batch:
            break
        all_markets.extend(batch)
        offset += batch_size
        if len(batch) < batch_size:
            break

    MARKETS_SCANNED.inc(len(all_markets))
    logger.info(f"Fetched {len(all_markets)} active markets from Gamma API")

    # Filter by volume + liquidity thresholds
    min_vol = ctx.dynamic_config.min_market_volume
    min_liq = ctx.dynamic_config.min_market_liquidity
    candidates = [
        m
        for m in all_markets
        if m.volume >= min_vol
        and m.liquidity >= min_liq
        and _has_valid_tokens(m)
        and _not_expired(m)
    ]

    logger.info(
        f"Tier 0 filter: {len(candidates)} candidates "
        f"(vol >= ${min_vol:,.0f}, liq >= ${min_liq:,.0f})"
    )
    return candidates


def _has_valid_tokens(market: GammaMarket) -> bool:
    """Check that market has CLOB token IDs for trading."""
    return len(market.clob_token_ids) >= 2


def _not_expired(market: GammaMarket) -> bool:
    """Check that market hasn't already expired."""
    if not market.end_date_iso:
        return True
    try:
        end = datetime.fromisoformat(market.end_date_iso.replace("Z", "+00:00"))
        return end > datetime.now(timezone.utc)
    except (ValueError, AttributeError):
        return True


def rank_markets(markets: list[GammaMarket]) -> list[GammaMarket]:
    """Rank markets by a composite score of volume and liquidity."""
    return sorted(
        markets,
        key=lambda m: Decimal(str(m.volume)) * Decimal("0.6") + Decimal(str(m.liquidity)) * Decimal("0.4"),
        reverse=True,
    )


async def gather_market_context(
    market: GammaMarket, ctx: TradingContext
) -> dict:
    """Gather context for a market before LLM analysis.

    Returns a dict of context info (prices, volume, description, etc.)
    that gets passed to the probability engine.
    """
    # Get current price from CLOB if available
    yes_price = 0.5
    no_price = 0.5
    if market.outcome_prices and len(market.outcome_prices) >= 2:
        try:
            yes_price = float(market.outcome_prices[0])
            no_price = float(market.outcome_prices[1])
        except (ValueError, IndexError):
            pass

    return {
        "market_id": market.condition_id,
        "question": market.question,
        "description": market.description,
        "category": market.category,
        "end_date": market.end_date_iso or "Unknown",
        "volume": market.volume,
        "liquidity": market.liquidity,
        "market_price": yes_price,
        "yes_price": yes_price,
        "no_price": no_price,
    }


async def run_scan_cycle(ctx: TradingContext) -> list[GammaMarket]:
    """Run one full scan cycle: fetch, filter, rank."""
    candidates = await fetch_candidate_markets(ctx)
    ranked = rank_markets(candidates)
    MARKETS_WITH_EDGE.set(len(ranked))
    return ranked
