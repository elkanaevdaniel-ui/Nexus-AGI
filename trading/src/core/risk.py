"""Risk manager with circuit breakers, position limits, and drawdown tracking."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

from loguru import logger

from src.data.schemas import EdgeResult, RiskCheckResult
from src.utils.metrics import CIRCUIT_BREAKER_TRIPS, DAILY_LOSS_PCT, MAX_DRAWDOWN_PCT

if TYPE_CHECKING:
    from src.context import TradingContext

_ZERO = Decimal(0)


class RiskManager:
    """Central risk manager enforcing position limits and circuit breakers.

    Circuit breakers are SACRED — never bypassable programmatically.
    """

    def __init__(self) -> None:
        self._daily_pnl: Decimal = _ZERO
        self._peak_value: Decimal = _ZERO
        self._current_value: Decimal = _ZERO
        self._daily_trades: int = 0
        self._circuit_breakers_tripped: set[str] = set()
        self._last_reset: datetime = datetime.now(timezone.utc)

    @property
    def is_any_breaker_tripped(self) -> bool:
        return len(self._circuit_breakers_tripped) > 0

    @property
    def tripped_breakers(self) -> set[str]:
        return set(self._circuit_breakers_tripped)

    def update_portfolio_value(self, total_value: float | Decimal) -> None:
        """Update tracked portfolio value for drawdown calculation."""
        v = Decimal(str(total_value)) if not isinstance(total_value, Decimal) else total_value
        self._current_value = v
        if v > self._peak_value:
            self._peak_value = v

    def record_pnl(self, pnl: float | Decimal) -> None:
        """Record PnL for daily tracking."""
        p = Decimal(str(pnl)) if not isinstance(pnl, Decimal) else pnl
        self._daily_pnl += p
        self._daily_trades += 1

    def reset_daily(self) -> None:
        """Reset daily counters and clear daily circuit breakers."""
        self._daily_pnl = _ZERO
        self._daily_trades = 0
        self._circuit_breakers_tripped.discard("daily_loss")
        self._last_reset = datetime.now(timezone.utc)
        logger.info("Daily risk counters and daily_loss breaker reset")

    def _maybe_reset_daily(self) -> None:
        """Automatically reset daily counters if a new UTC day has started."""
        now = datetime.now(timezone.utc)
        if now.date() > self._last_reset.date():
            logger.info("New UTC day detected — performing automatic daily reset")
            self.reset_daily()

    async def check(
        self,
        market_id: str,
        edge: EdgeResult,
        open_positions_count: int,
        portfolio_value: float | Decimal,
        ctx: TradingContext,
    ) -> RiskCheckResult:
        """Run all risk checks before allowing a trade.

        Returns approved=False if any check fails.
        """
        dyn = ctx.dynamic_config
        pv = Decimal(str(portfolio_value)) if not isinstance(portfolio_value, Decimal) else portfolio_value

        # 0. Automatic daily reset at midnight UTC
        self._maybe_reset_daily()

        # 1. Circuit breakers — absolute block
        if self.is_any_breaker_tripped:
            return RiskCheckResult(
                approved=False,
                reason=f"Circuit breaker active: {self._circuit_breakers_tripped}",
                breaker_type="circuit_breaker",
            )

        # 2. Trading paused
        if ctx.trading_paused:
            return RiskCheckResult(
                approved=False,
                reason="Trading is paused",
            )

        # 3. Max open positions
        if open_positions_count >= dyn.max_open_positions:
            return RiskCheckResult(
                approved=False,
                reason=f"Max positions reached ({open_positions_count}/{dyn.max_open_positions})",
            )

        # 4. Daily loss limit
        if pv > _ZERO:
            daily_loss_pct = abs(min(_ZERO, self._daily_pnl)) / pv
            DAILY_LOSS_PCT.set(float(daily_loss_pct))
            if float(daily_loss_pct) >= dyn.max_daily_loss_pct:
                await self._trip_breaker(
                    "daily_loss", float(daily_loss_pct), dyn.max_daily_loss_pct, ctx
                )
                return RiskCheckResult(
                    approved=False,
                    reason=f"Daily loss limit hit ({float(daily_loss_pct):.1%} >= {dyn.max_daily_loss_pct:.1%})",
                    breaker_type="daily_loss",
                )

        # 5. Max drawdown
        if self._peak_value > _ZERO:
            drawdown = (self._peak_value - self._current_value) / self._peak_value
            MAX_DRAWDOWN_PCT.set(float(drawdown))
            if float(drawdown) >= dyn.max_drawdown_pct:
                await self._trip_breaker(
                    "drawdown", float(drawdown), dyn.max_drawdown_pct, ctx
                )
                return RiskCheckResult(
                    approved=False,
                    reason=f"Drawdown limit hit ({float(drawdown):.1%} >= {dyn.max_drawdown_pct:.1%})",
                    breaker_type="drawdown",
                )

        # 6. Minimum edge threshold (already checked in pipeline but double-check)
        edge_mag = float(edge.magnitude)
        if edge_mag < dyn.min_edge_threshold:
            return RiskCheckResult(
                approved=False,
                reason=f"Edge {edge_mag:.3f} below threshold {dyn.min_edge_threshold}",
            )

        return RiskCheckResult(approved=True, reason="All risk checks passed")

    async def _trip_breaker(
        self,
        breaker_type: str,
        trigger_value: float,
        threshold: float,
        ctx: TradingContext,
    ) -> None:
        """Trip a circuit breaker — logs the event and pauses trading."""
        self._circuit_breakers_tripped.add(breaker_type)
        ctx.trading_paused = True

        CIRCUIT_BREAKER_TRIPS.labels(reason=breaker_type).inc()

        await ctx.repo.log_circuit_breaker({
            "breaker_type": breaker_type,
            "trigger_value": trigger_value,
            "threshold": threshold,
            "action_taken": "trading_paused",
        })

        logger.critical(
            f"CIRCUIT BREAKER TRIPPED: {breaker_type} "
            f"(value={trigger_value:.4f}, threshold={threshold:.4f})"
        )

    async def reset_breaker(self, breaker_type: str, ctx: TradingContext) -> bool:
        """Manually reset a circuit breaker (requires elevated auth)."""
        if breaker_type in self._circuit_breakers_tripped:
            self._circuit_breakers_tripped.discard(breaker_type)
            logger.warning(f"Circuit breaker manually reset: {breaker_type}")
            return True
        return False

    async def restore_state(self, ctx: TradingContext) -> None:
        """Restore risk manager state from database after restart."""
        snapshot = await ctx.repo.get_latest_portfolio_snapshot()
        if snapshot:
            self._peak_value = Decimal(str(snapshot.total_value))
            self._current_value = Decimal(str(snapshot.total_value))
            self._daily_pnl = Decimal(str(snapshot.daily_pnl))
            # Restore _last_reset from the snapshot timestamp so that
            # _maybe_reset_daily can detect if a new UTC day has started
            # since the snapshot was taken (fixes stale daily counters
            # surviving across restarts).
            snapshot_ts = snapshot.created_at
            if snapshot_ts.tzinfo is None:
                snapshot_ts = snapshot_ts.replace(tzinfo=timezone.utc)
            self._last_reset = snapshot_ts
            logger.info(
                f"Restored risk state: peak={self._peak_value:.2f}, "
                f"daily_pnl={self._daily_pnl:.2f}"
            )
        # Auto-reset daily counters if we restored stale data from a prior day.
        self._maybe_reset_daily()
