"""Background task loops for the trading engine."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from src.context import TradingContext


async def scan_loop(ctx: TradingContext) -> None:
    """Periodic market scan and trade execution loop."""
    from src.core.pipeline import run_pipeline_cycle

    logger.info("Scan loop started")
    while True:
        try:
            results = await run_pipeline_cycle(ctx)
            if results:
                logger.info(f"Pipeline cycle produced {len(results)} trade(s)")
        except asyncio.CancelledError:
            logger.info("Scan loop cancelled")
            return
        except Exception as e:
            logger.error(f"Scan loop error: {e}")

        await asyncio.sleep(ctx.dynamic_config.scan_interval_seconds)


async def reconciliation_loop(ctx: TradingContext) -> None:
    """Periodic reconciliation loop (every 15 minutes)."""
    from src.core.reconciliation import run_reconciliation_cycle

    logger.info("Reconciliation loop started")
    while True:
        try:
            await asyncio.sleep(900)  # 15 minutes
            count = await run_reconciliation_cycle(ctx)
            if count > 0:
                logger.warning(f"Reconciliation found {count} discrepancies")
        except asyncio.CancelledError:
            logger.info("Reconciliation loop cancelled")
            return
        except Exception as e:
            logger.error(f"Reconciliation loop error: {e}")
            await asyncio.sleep(60)


async def resolution_loop(ctx: TradingContext) -> None:
    """Periodic resolution check loop (every 10 minutes)."""
    from src.core.resolution import check_resolutions

    logger.info("Resolution loop started")
    while True:
        try:
            await asyncio.sleep(600)  # 10 minutes
            if ctx.portfolio and ctx.calibration_tracker:
                settlements = await check_resolutions(
                    ctx, ctx.portfolio, ctx.calibration_tracker
                )
                if settlements:
                    logger.info(f"Settled {len(settlements)} position(s)")
        except asyncio.CancelledError:
            logger.info("Resolution loop cancelled")
            return
        except Exception as e:
            logger.error(f"Resolution loop error: {e}")
            await asyncio.sleep(60)


async def arbitrage_loop(ctx: TradingContext) -> None:
    """Periodic arbitrage scan loop (every 5 minutes)."""
    from src.core.arbitrage import execute_arbitrage, run_arbitrage_scan

    logger.info("Arbitrage loop started")
    while True:
        try:
            await asyncio.sleep(300)  # 5 minutes
            opportunities = await run_arbitrage_scan(ctx)
            for arb in opportunities:
                await execute_arbitrage(arb, ctx)
        except asyncio.CancelledError:
            logger.info("Arbitrage loop cancelled")
            return
        except Exception as e:
            logger.error(f"Arbitrage loop error: {e}")
            await asyncio.sleep(60)


async def price_update_loop(ctx: TradingContext) -> None:
    """Periodic price update for open positions (every 2 minutes)."""
    from src.core.stop_loss import check_stop_losses

    logger.info("Price update loop started")
    while True:
        try:
            await asyncio.sleep(120)  # 2 minutes
            if ctx.portfolio:
                await ctx.portfolio.update_prices(ctx)
                # Also update risk manager with current portfolio value
                if ctx.risk_manager:
                    summary = await ctx.portfolio.get_summary(ctx)
                    ctx.risk_manager.update_portfolio_value(summary.total_value)

                # Check stop-losses after price update
                stop_loss_events = await check_stop_losses(ctx)
                if stop_loss_events:
                    logger.warning(
                        f"Stop-loss: {len(stop_loss_events)} position(s) auto-closed"
                    )
        except asyncio.CancelledError:
            logger.info("Price update loop cancelled")
            return
        except Exception as e:
            logger.error(f"Price update loop error: {e}")
            await asyncio.sleep(30)


async def start_background_tasks(ctx: TradingContext) -> list[asyncio.Task]:
    """Start all background task loops. Returns task handles for shutdown."""
    tasks = [
        asyncio.create_task(scan_loop(ctx), name="scan_loop"),
        asyncio.create_task(reconciliation_loop(ctx), name="reconciliation_loop"),
        asyncio.create_task(resolution_loop(ctx), name="resolution_loop"),
        asyncio.create_task(arbitrage_loop(ctx), name="arbitrage_loop"),
        asyncio.create_task(price_update_loop(ctx), name="price_update_loop"),
    ]
    logger.info(f"Started {len(tasks)} background tasks")
    return tasks


async def stop_background_tasks(tasks: list[asyncio.Task]) -> None:
    """Gracefully cancel all background tasks."""
    for task in tasks:
        task.cancel()

    results = await asyncio.gather(*tasks, return_exceptions=True)
    for task, result in zip(tasks, results):
        if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError):
            logger.error(f"Task {task.get_name()} failed during shutdown: {result}")

    logger.info(f"Stopped {len(tasks)} background tasks")
