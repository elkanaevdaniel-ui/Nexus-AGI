"""Trading pipeline — chains scanner → probability → edge → kelly → risk → executor."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import TYPE_CHECKING

from loguru import logger

from src.core.edge import calculate_edge
from src.core.executor import safe_place_order
from src.core.kelly import fee_adjusted_kelly
from src.core.probability import estimate_probability_consensus
from src.core.scanner import gather_market_context, run_scan_cycle
from src.data.schemas import GammaMarket, TradeDecision
from src.signals.aggregator import SignalAggregator, format_signals_for_prompt

if TYPE_CHECKING:
    from src.context import TradingContext

# Module-level singleton — collectors maintain auth tokens and dedup state
_aggregator = SignalAggregator()


async def evaluate_market(
    market: GammaMarket,
    ctx: TradingContext,
) -> TradeDecision:
    """Run the full evaluation pipeline for a single market.

    Steps:
        1. Gather market context (prices, metadata)
        2. Estimate probability via multi-LLM consensus
        3. Calculate edge after fees
        4. Size position via Kelly criterion
        5. Risk check
        6. Return trade decision (BUY/SELL/SKIP)
    """
    dyn = ctx.dynamic_config

    # 1. Gather market context + external signals in parallel
    context, market_signals = await asyncio.gather(
        gather_market_context(market, ctx),
        _aggregator.gather(market.condition_id, market.question, ctx),
    )
    market_price = context["market_price"]

    # Inject signal summary into context for LLM
    context["signals"] = format_signals_for_prompt(market_signals)
    context["signal_sentiment"] = market_signals.overall_sentiment
    context["signal_count"] = market_signals.signal_count

    # 2. Probability estimation (now with signal context)
    consensus = await estimate_probability_consensus(context, ctx)
    if consensus.confidence == "low" and consensus.spread > 0.25:
        return TradeDecision(
            action="SKIP",
            reason=f"Low confidence with high spread ({consensus.spread:.2f})",
            market_id=market.condition_id,
            estimate=consensus,
        )

    # 3. Edge calculation
    edge = calculate_edge(
        estimate=consensus,
        market_price=market_price,
        fee_rate_bps=dyn.fee_rate_bps,
    )

    if float(edge.magnitude) < dyn.min_edge_threshold:
        return TradeDecision(
            action="SKIP",
            reason=f"Edge {float(edge.magnitude):.4f} below threshold {dyn.min_edge_threshold}",
            market_id=market.condition_id,
            edge=edge,
            estimate=consensus,
        )

    # 4. Kelly sizing
    portfolio = ctx.portfolio
    if not portfolio:
        return TradeDecision(
            action="SKIP",
            reason="No portfolio tracker available",
            market_id=market.condition_id,
        )

    summary = await portfolio.get_summary(ctx)
    bankroll = float(summary.total_value)

    kelly = fee_adjusted_kelly(
        estimated_prob=consensus.probability,
        market_price=market_price,
        fee_rate_bps=dyn.fee_rate_bps,
        kelly_multiplier=dyn.kelly_fraction,
        bankroll=bankroll,
        max_position_pct=dyn.max_single_position_pct,
    )

    if kelly.position_size_usd <= Decimal(0):
        return TradeDecision(
            action="SKIP",
            reason="Kelly sizing returned zero position",
            market_id=market.condition_id,
            edge=edge,
            kelly=kelly,
            estimate=consensus,
        )

    # 5. Risk check
    risk_mgr = ctx.risk_manager
    if not risk_mgr:
        return TradeDecision(
            action="SKIP",
            reason="No risk manager available",
            market_id=market.condition_id,
        )

    open_positions = await ctx.repo.get_open_positions()
    risk_result = await risk_mgr.check(
        market_id=market.condition_id,
        edge=edge,
        open_positions_count=len(open_positions),
        portfolio_value=bankroll,
        ctx=ctx,
    )

    if not risk_result.approved:
        return TradeDecision(
            action="SKIP",
            reason=f"Risk rejected: {risk_result.reason}",
            market_id=market.condition_id,
            edge=edge,
            kelly=kelly,
            estimate=consensus,
        )

    # 6. Build trade decision
    # Determine token ID — BUY YES token if edge direction is BUY, else NO token
    if edge.direction == "BUY":
        token_id = market.clob_token_ids[0] if market.clob_token_ids else ""
        price = Decimal(str(market_price))
    else:
        token_id = market.clob_token_ids[1] if len(market.clob_token_ids) > 1 else ""
        price = Decimal(str(1.0 - market_price))

    return TradeDecision(
        action=edge.direction,
        reason=f"Edge {float(edge.magnitude):.4f}, Kelly size ${kelly.position_size_usd}",
        market_id=market.condition_id,
        token_id=token_id,
        size_usd=kelly.position_size_usd,
        price=price,
        edge=edge,
        kelly=kelly,
        estimate=consensus,
    )


async def execute_decision(
    decision: TradeDecision,
    ctx: TradingContext,
) -> dict:
    """Execute a trade decision and update portfolio.

    Only executes BUY/SELL decisions; SKIPs are no-ops.
    """
    if decision.action == "SKIP":
        return {"status": "skipped", "reason": decision.reason}

    # Execute the order
    result = await safe_place_order(decision, ctx)

    # If filled, update portfolio
    if result.get("status") == "filled" and ctx.portfolio:
        fill = result.get("fill", {})
        await ctx.portfolio.open_position(
            market_id=decision.market_id,
            token_id=decision.token_id,
            side=decision.action,
            quantity=Decimal(str(fill.get("quantity", 0))),
            price=Decimal(str(fill.get("price", 0))),
            fee=Decimal(str(fill.get("fee", 0))),
            ctx=ctx,
        )

        # Update risk manager with portfolio value
        if ctx.risk_manager:
            summary = await ctx.portfolio.get_summary(ctx)
            ctx.risk_manager.update_portfolio_value(summary.total_value)

    return result


async def store_pending_trade(
    decision: TradeDecision,
    market: GammaMarket,
    ctx: TradingContext,
) -> dict:
    """Store a trade decision as pending for user approval."""
    trade_data = {
        "market_id": decision.market_id,
        "question": market.question,
        "action": decision.action,
        "token_id": decision.token_id,
        "size_usd": decision.size_usd,
        "price": decision.price,
        "edge_magnitude": decision.edge.magnitude if decision.edge else Decimal(0),
        "estimated_prob": decision.edge.estimated_prob if decision.edge else Decimal(0),
        "market_price": decision.edge.market_price if decision.edge else Decimal(0),
        "kelly_fraction": decision.kelly.adjusted_fraction if decision.kelly else Decimal(0),
        "confidence": decision.estimate.confidence if decision.estimate else "medium",
        "reasoning": decision.estimate.reasoning if decision.estimate else "",
        "status": "pending",
    }
    pending = await ctx.repo.create_pending_trade(trade_data)
    logger.info(
        f"Pending trade stored: {decision.action} {market.question[:50]} "
        f"size=${decision.size_usd} (awaiting approval)"
    )

    # Notify user via Telegram
    if ctx.telegram and ctx.telegram.enabled:
        await ctx.telegram.send_pending_trade_notification(
            trade_id=pending.id,
            question=market.question,
            estimated_prob=trade_data["estimated_prob"],
            market_price=trade_data["market_price"],
            edge=trade_data["edge_magnitude"],
            size_usd=trade_data["size_usd"],
            confidence=trade_data["confidence"],
        )

    return {"status": "pending", "pending_trade_id": pending.id}


async def run_pipeline_cycle(ctx: TradingContext) -> list[dict]:
    """Run one full pipeline cycle: scan → evaluate → store pending.

    Trade decisions are stored as pending for user approval
    instead of being auto-executed.

    Returns list of results for each market evaluated.
    """
    if ctx.trading_paused:
        logger.debug("Trading paused — skipping pipeline cycle")
        return []

    # Expire stale pending trades (older than 2 hours)
    expired = await ctx.repo.expire_old_pending_trades(max_age_hours=2)
    if expired:
        logger.info(f"Expired {expired} stale pending trade(s)")

    # Scan for candidate markets
    markets = await run_scan_cycle(ctx)

    results: list[dict] = []
    for market in markets[:10]:  # Evaluate top 10 candidates per cycle
        try:
            decision = await evaluate_market(market, ctx)

            if decision.action != "SKIP":
                logger.info(
                    f"Trade signal: {decision.action} {decision.market_id} "
                    f"size=${decision.size_usd} edge={float(decision.edge.magnitude) if decision.edge else 0:.4f}"
                )
                result = await store_pending_trade(decision, market, ctx)
                results.append({
                    "market_id": market.condition_id,
                    "action": decision.action,
                    "result": result,
                })
            else:
                logger.debug(
                    f"SKIP {market.question[:50]}: {decision.reason}"
                )

        except Exception as e:
            logger.error(f"Pipeline error for market {market.id}: {e}")

    # Save portfolio snapshot after cycle
    if ctx.portfolio and results:
        await ctx.portfolio.save_snapshot(ctx)

    return results
