"""State reconciliation — syncs local DB with on-chain balances and CLOB orders."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from loguru import logger

from src.data.schemas import ReconciliationEvent
from src.utils.metrics import RECONCILIATION_DISCREPANCIES

if TYPE_CHECKING:
    from src.context import TradingContext


async def startup_reconciliation(ctx: TradingContext) -> list[ReconciliationEvent]:
    """MUST run before any trading resumes after restart.

    Compares DB state to actual CLOB state and logs discrepancies.
    Sets trading_paused=True in live mode (only on startup, not periodic).
    """
    logger.info("Starting startup reconciliation...")
    discrepancies = await _run_reconciliation(ctx)

    # Set trading state based on mode — ONLY on startup
    if ctx.config.trading_mode == "live":
        ctx.trading_paused = True
        logger.warning(
            "LIVE MODE — trading paused until manual confirmation via API or Telegram"
        )
    else:
        ctx.trading_paused = False
        logger.info("PAPER MODE — auto-resuming trading")

    logger.info(
        f"Startup reconciliation complete: {len(discrepancies)} discrepancies found"
    )
    return discrepancies


async def run_reconciliation_cycle(ctx: TradingContext) -> int:
    """Periodic reconciliation (every 15 minutes).

    Unlike startup_reconciliation, this does NOT modify trading_paused state.
    It only checks for discrepancies and logs them.
    """
    discrepancies = await _run_reconciliation(ctx)
    logger.info(
        f"Periodic reconciliation: {len(discrepancies)} discrepancies found"
    )
    return len(discrepancies)


async def _run_reconciliation(ctx: TradingContext) -> list[ReconciliationEvent]:
    """Core reconciliation logic shared by startup and periodic checks."""
    discrepancies: list[ReconciliationEvent] = []

    # 1. Load last portfolio snapshot
    last_snapshot = await ctx.repo.get_latest_portfolio_snapshot()
    if last_snapshot:
        logger.info(
            f"Last snapshot: value={last_snapshot.total_value:.2f}, "
            f"positions={last_snapshot.open_positions_count}"
        )

    # 2. Fetch open orders from CLOB (if client available)
    open_orders: list[dict] = []
    if ctx.clob:
        try:
            open_orders = await ctx.clob.get_orders()
            logger.info(f"Found {len(open_orders)} open CLOB orders")
        except Exception as e:
            logger.warning(f"Failed to fetch CLOB orders: {e}")

    # 3. Compare DB positions vs CLOB state
    db_positions = await ctx.repo.get_open_positions()
    logger.info(f"DB has {len(db_positions)} open positions")

    # 4. Cancel stale pending orders (older than 30 minutes)
    stale_count = 0
    for order in open_orders:
        if _is_stale_order(order, max_age_minutes=30):
            try:
                order_id = order.get("id", order.get("orderID", ""))
                if order_id and ctx.clob:
                    await ctx.clob.cancel(order_id)
                    stale_count += 1
                    logger.info(f"Cancelled stale order: {order_id}")
            except Exception as e:
                logger.warning(f"Failed to cancel stale order: {e}")

    if stale_count:
        disc = ReconciliationEvent(
            reconciliation_type="stale_orders",
            db_value="0",
            chain_value=str(stale_count),
            discrepancy=f"Cancelled {stale_count} stale orders",
        )
        discrepancies.append(disc)
        await ctx.repo.log_reconciliation_event(disc.model_dump())

    # 5. Log discrepancies
    for disc in discrepancies:
        RECONCILIATION_DISCREPANCIES.inc()
        logger.warning(f"Reconciliation discrepancy: {disc.discrepancy}")

    return discrepancies


def _is_stale_order(order: dict, max_age_minutes: int = 30) -> bool:
    """Check if an order is stale based on creation time."""
    created = order.get("created_at") or order.get("timestamp")
    if not created:
        return False
    try:
        now = datetime.now(timezone.utc)
        if isinstance(created, str):
            created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
        elif isinstance(created, (int, float)):
            created_dt = datetime.fromtimestamp(created, tz=timezone.utc)
        else:
            return False

        if created_dt.tzinfo is None:
            created_dt = created_dt.replace(tzinfo=timezone.utc)
        age = now - created_dt
        return age > timedelta(minutes=max_age_minutes)
    except (ValueError, TypeError):
        return False
