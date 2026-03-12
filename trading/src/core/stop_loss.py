"""Stop-loss checker — auto-sells positions that breach the loss threshold."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from src.context import TradingContext
    from src.data.models import Position


async def check_stop_losses(ctx: TradingContext) -> list[dict]:
    """Check all open positions against the stop-loss threshold.

    If a position's unrealized PnL drops below -stop_loss_pct of the cost basis,
    close the position via the executor.

    Returns list of stop-loss events triggered.
    """
    from src.core.executor import safe_place_order
    from src.data.schemas import TradeDecision

    stop_loss_pct = Decimal(str(ctx.dynamic_config.stop_loss_pct))
    positions = await ctx.repo.get_open_positions()
    events: list[dict] = []

    for pos in positions:
        if pos.cost_basis <= 0:
            continue

        # Calculate loss percentage relative to cost basis
        loss_pct = -pos.unrealized_pnl / pos.cost_basis
        if loss_pct < stop_loss_pct:
            continue

        logger.warning(
            f"STOP-LOSS triggered for {pos.market_id}: "
            f"loss={float(loss_pct):.1%} (threshold={float(stop_loss_pct):.1%}), "
            f"entry=${float(pos.avg_entry_price):.4f} current=${float(pos.current_price):.4f}"
        )

        # Build a SELL decision to close the position
        sell_side = "SELL"
        decision = TradeDecision(
            action=sell_side,
            reason=f"Stop-loss at {float(loss_pct):.1%} (threshold {float(stop_loss_pct):.1%})",
            market_id=pos.market_id,
            token_id=pos.token_id,
            size_usd=abs(pos.unrealized_pnl + pos.cost_basis),  # Current value
            price=pos.current_price,
        )

        try:
            result = await safe_place_order(decision, ctx)

            if result.get("status") == "filled" and ctx.portfolio:
                fill = result.get("fill", {})
                await ctx.portfolio.close_position(
                    position_id=pos.id,
                    exit_price=pos.current_price,
                    quantity=None,  # Close entire position
                    fee=Decimal(str(fill.get("fee", 0))),
                    ctx=ctx,
                )

            event = {
                "position_id": pos.id,
                "market_id": pos.market_id,
                "loss_pct": float(loss_pct),
                "entry_price": float(pos.avg_entry_price),
                "exit_price": float(pos.current_price),
                "realized_loss": float(pos.unrealized_pnl),
                "result": result.get("status", "unknown"),
            }
            events.append(event)

            # Create an alert for the stop-loss
            await ctx.repo.create_alert({
                "alert_type": "risk",
                "severity": "warning",
                "title": f"Stop-loss triggered: {pos.market_id[:20]}",
                "message": (
                    f"Position closed at {float(loss_pct):.1%} loss. "
                    f"Entry: ${float(pos.avg_entry_price):.4f}, "
                    f"Exit: ${float(pos.current_price):.4f}, "
                    f"Loss: ${float(pos.unrealized_pnl):.2f}"
                ),
            })

        except Exception as e:
            logger.error(f"Stop-loss execution failed for {pos.market_id}: {e}")

    if events:
        logger.info(f"Stop-loss check: {len(events)} position(s) closed")

    return events
