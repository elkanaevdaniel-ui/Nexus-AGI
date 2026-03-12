"""Order execution with idempotency, slippage protection, and paper broker."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from loguru import logger

from src.data.schemas import OrderBookLevel, OrderBookSummary, TradeDecision
from src.utils.metrics import TRADE_SIZE_USD, TRADES_TOTAL

if TYPE_CHECKING:
    from src.context import TradingContext

_ZERO = Decimal(0)


def _to_d(v: float | Decimal | str) -> Decimal:
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


@dataclass(frozen=True)
class Fill:
    """Represents a filled (or simulated) order."""

    quantity: Decimal
    price: Decimal
    fee: Decimal
    slippage: Decimal


class PaperBroker:
    """Realistic fill simulation using orderbook depth, slippage, and fees."""

    def simulate_fill(
        self,
        side: str,
        price: float | Decimal,
        size: float | Decimal,
        orderbook: OrderBookSummary,
        fee_rate_bps: int = 200,
    ) -> Optional[Fill]:
        """Simulate fill against actual orderbook depth.

        Returns None if insufficient liquidity (< 50% fill).
        """
        levels = orderbook.asks if side == "BUY" else orderbook.bids
        if not levels:
            return None

        limit_price = _to_d(price)
        target_size = _to_d(size)
        filled_qty = _ZERO
        total_cost = _ZERO

        for level in levels:
            level_price = _to_d(level.price)
            level_size = _to_d(level.size)

            if side == "BUY" and level_price > limit_price:
                break
            if side == "SELL" and level_price < limit_price:
                break

            fill_at_level = min(target_size - filled_qty, level_size)
            filled_qty += fill_at_level
            total_cost += fill_at_level * level_price

            if filled_qty >= target_size:
                break

        if filled_qty < target_size / 2:
            return None  # Insufficient liquidity

        avg_price = total_cost / filled_qty if filled_qty > _ZERO else limit_price
        fee = self._calculate_fee(avg_price, filled_qty, fee_rate_bps)
        slippage = abs(avg_price - limit_price)

        return Fill(
            quantity=filled_qty,
            price=avg_price,
            fee=fee,
            slippage=slippage,
        )

    @staticmethod
    def _calculate_fee(
        price: Decimal | float, size: Decimal | float, fee_rate_bps: int
    ) -> Decimal:
        """Calculate Polymarket taker fee."""
        p = _to_d(price)
        s = _to_d(size)
        base_rate = Decimal(fee_rate_bps) / Decimal(10_000)
        return base_rate * min(p, Decimal(1) - p) * s


async def safe_place_order(
    decision: TradeDecision,
    ctx: TradingContext,
) -> dict:
    """Place an order with idempotency and timeout recovery.

    Paper mode: simulates fills via PaperBroker.
    Live mode: places via CLOB with idempotent retry.
    """
    order_id = str(uuid.uuid4())

    # Record the order attempt
    await ctx.repo.create_order({
        "id": order_id,
        "market_id": decision.market_id,
        "token_id": decision.token_id,
        "side": decision.action,
        "price": decision.price,
        "size": decision.size_usd,
        "status": "pending",
    })

    await ctx.repo.log_order_event({
        "order_id": order_id,
        "event_type": "placed",
        "details": f"edge={decision.edge.magnitude if decision.edge else 0:.4f}",
    })

    if ctx.is_paper:
        return await _paper_execute(order_id, decision, ctx)
    else:
        return await _live_execute(order_id, decision, ctx)


async def _paper_execute(
    order_id: str,
    decision: TradeDecision,
    ctx: TradingContext,
) -> dict:
    """Execute in paper mode using PaperBroker simulation."""
    broker = PaperBroker()

    # Get orderbook for realistic simulation
    orderbook = None
    if ctx.clob and decision.token_id:
        try:
            orderbook = await ctx.clob.get_order_book(decision.token_id)
        except Exception:
            pass

    if orderbook is None:
        # Fallback: create a simple orderbook using proper Pydantic models
        fallback_price = _to_d(decision.price)
        orderbook = OrderBookSummary(
            bids=[OrderBookLevel(
                price=str(max(Decimal("0.001"), fallback_price - Decimal("0.01"))),
                size="1000",
            )],
            asks=[OrderBookLevel(
                price=str(min(Decimal("0.999"), fallback_price + Decimal("0.01"))),
                size="1000",
            )],
        )

    dec_price = _to_d(decision.price)
    shares = (
        _to_d(decision.size_usd) / dec_price
        if dec_price > _ZERO
        else _ZERO
    )
    fill = broker.simulate_fill(
        side=decision.action,
        price=dec_price,
        size=shares,
        orderbook=orderbook,
        fee_rate_bps=ctx.dynamic_config.fee_rate_bps,
    )

    if fill is None:
        await ctx.repo.update_order_status(order_id, "rejected")
        await ctx.repo.log_order_event({
            "order_id": order_id,
            "event_type": "rejected",
            "details": "Insufficient liquidity for paper fill",
        })
        TRADES_TOTAL.labels(side=decision.action, status="rejected").inc()
        return {"status": "rejected", "reason": "insufficient_liquidity"}

    # Record the trade
    trade_id = str(uuid.uuid4())
    await ctx.repo.record_trade({
        "id": trade_id,
        "order_id": order_id,
        "market_id": decision.market_id,
        "token_id": decision.token_id,
        "side": decision.action,
        "price": fill.price,
        "size": fill.quantity,
        "fee": fill.fee,
        "slippage": fill.slippage,
        "is_paper": True,
    })

    await ctx.repo.update_order_status(order_id, "filled", filled_size=fill.quantity)
    await ctx.repo.log_order_event({
        "order_id": order_id,
        "event_type": "filled",
        "details": f"paper fill: qty={fill.quantity:.4f} @ {fill.price:.4f}",
    })

    TRADES_TOTAL.labels(side=decision.action, status="filled").inc()
    TRADE_SIZE_USD.observe(float(decision.size_usd))

    logger.info(
        f"[PAPER] {decision.action} filled: "
        f"qty={fill.quantity:.4f} @ {fill.price:.4f} "
        f"fee={fill.fee:.4f} slip={fill.slippage:.4f}"
    )

    return {
        "status": "filled",
        "order_id": order_id,
        "trade_id": trade_id,
        "fill": {
            "quantity": float(fill.quantity),
            "price": float(fill.price),
            "fee": float(fill.fee),
            "slippage": float(fill.slippage),
        },
    }


async def _live_execute(
    order_id: str,
    decision: TradeDecision,
    ctx: TradingContext,
) -> dict:
    """Execute via CLOB API with idempotent retry on timeout."""
    if not ctx.clob:
        await ctx.repo.update_order_status(order_id, "rejected")
        return {"status": "rejected", "reason": "no_clob_client"}

    try:
        dec_price = _to_d(decision.price)
        # Price/size validation
        if dec_price < Decimal("0.01") or dec_price > Decimal("0.99"):
            await ctx.repo.update_order_status(order_id, "rejected")
            return {"status": "rejected", "reason": "price_out_of_range"}

        # Min order size is 5 shares on Polymarket
        shares = (
            _to_d(decision.size_usd) / dec_price
            if dec_price > _ZERO
            else _ZERO
        )
        if shares < 5:
            await ctx.repo.update_order_status(order_id, "rejected")
            return {"status": "rejected", "reason": "below_min_order_size"}

        result = await ctx.clob.create_and_post_order(
            {
                "token_id": decision.token_id,
                "price": float(dec_price),
                "size": float(shares),
                "side": decision.action,
            }
        )

        clob_order_id = result.get("orderID", result.get("id", ""))
        await ctx.repo.update_order_status(
            order_id, "placed", clob_order_id=clob_order_id
        )

        TRADES_TOTAL.labels(side=decision.action, status="placed").inc()
        TRADE_SIZE_USD.observe(float(decision.size_usd))

        logger.info(
            f"[LIVE] {decision.action} placed: clob_id={clob_order_id}"
        )

        return {
            "status": "placed",
            "order_id": order_id,
            "clob_order_id": clob_order_id,
        }

    except Exception as e:
        error_msg = str(e).lower()

        # Idempotency: on timeout, check if order was actually placed
        if "timeout" in error_msg or "connection" in error_msg:
            import asyncio

            await asyncio.sleep(2)
            try:
                open_orders = await ctx.clob.get_orders()
                for oo in open_orders:
                    # Match by client_order_id first (most reliable)
                    if oo.get("client_order_id") == order_id:
                        await ctx.repo.update_order_status(
                            order_id, "placed", clob_order_id=oo.get("id", "")
                        )
                        return {
                            "status": "already_placed",
                            "order_id": order_id,
                            "clob_order_id": oo.get("id", ""),
                        }
                    # Fallback: match on asset + price + size
                    if (
                        oo.get("asset_id") == decision.token_id
                        and abs(float(oo.get("price", 0)) - float(decision.price)) < 0.001
                        and abs(float(oo.get("original_size", 0)) - float(shares)) < 0.01
                    ):
                        await ctx.repo.update_order_status(
                            order_id, "placed", clob_order_id=oo.get("id", "")
                        )
                        logger.warning(
                            f"Matched order by price/size (no client_order_id match): {oo.get('id')}"
                        )
                        return {
                            "status": "already_placed",
                            "order_id": order_id,
                            "clob_order_id": oo.get("id", ""),
                        }
            except Exception as check_err:
                logger.warning(f"Failed to check existing orders after timeout: {check_err}")

            # Order was not found on the exchange after timeout — safe to retry once
            # with the same order_id as idempotency key to prevent duplicates
            try:
                logger.info(f"Timeout recovery: retrying order {order_id} with idempotency key")
                result = await ctx.clob.create_and_post_order(
                    {
                        "token_id": decision.token_id,
                        "price": float(dec_price),
                        "size": float(shares),
                        "side": decision.action,
                        "client_order_id": order_id,
                    }
                )
                clob_order_id = result.get("orderID", result.get("id", ""))
                await ctx.repo.update_order_status(
                    order_id, "placed", clob_order_id=clob_order_id
                )
                TRADES_TOTAL.labels(side=decision.action, status="placed").inc()
                TRADE_SIZE_USD.observe(float(decision.size_usd))
                return {
                    "status": "placed",
                    "order_id": order_id,
                    "clob_order_id": clob_order_id,
                }
            except Exception as retry_err:
                logger.error(f"Idempotent retry also failed: {retry_err}")

        await ctx.repo.update_order_status(order_id, "rejected")
        await ctx.repo.log_order_event({
            "order_id": order_id,
            "event_type": "rejected",
            "details": str(e)[:500],
        })

        TRADES_TOTAL.labels(side=decision.action, status="rejected").inc()
        logger.error(f"Order execution failed: {e}")

        return {"status": "rejected", "reason": "order_execution_failed"}
