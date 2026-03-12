"""Portfolio tracker with cost basis, scaling in/out, and PnL tracking."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

from loguru import logger

from src.data.schemas import PortfolioSummary
from src.utils.metrics import (
    OPEN_POSITIONS,
    PORTFOLIO_VALUE,
    REALIZED_PNL,
    UNREALIZED_PNL,
)

if TYPE_CHECKING:
    from src.context import TradingContext

_ZERO = Decimal(0)
_ONE = Decimal(1)
_DUST = Decimal("0.001")


def _to_d(v: float | Decimal) -> Decimal:
    """Convert float to Decimal safely (avoids float repr issues)."""
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


class PortfolioTracker:
    """Tracks positions, PnL, and portfolio metrics.

    All monetary arithmetic uses Decimal to avoid floating-point
    accumulation errors.
    """

    def __init__(self, initial_bankroll: float | Decimal = 1000.0) -> None:
        self._cash_balance: Decimal = _to_d(initial_bankroll)
        self._initial_bankroll: Decimal = _to_d(initial_bankroll)
        self._realized_pnl: Decimal = _ZERO
        self._position_lock: asyncio.Lock = asyncio.Lock()

    @property
    def cash_balance(self) -> Decimal:
        return self._cash_balance

    async def restore_from_snapshot(self, ctx: TradingContext) -> bool:
        """Restore cash balance and realized PnL from the latest snapshot.

        Returns True if state was restored, False if no snapshot found.
        """
        snapshot = await ctx.repo.get_latest_portfolio_snapshot()
        if snapshot is None:
            return False
        self._cash_balance = _to_d(snapshot.cash_balance)
        self._realized_pnl = _to_d(snapshot.realized_pnl)
        logger.info(
            f"Restored portfolio state from snapshot: "
            f"cash={self._cash_balance}, realized_pnl={self._realized_pnl}"
        )
        return True

    async def open_position(
        self,
        market_id: str,
        token_id: str,
        side: str,
        quantity: float | Decimal,
        price: float | Decimal,
        fee: float | Decimal,
        ctx: TradingContext,
    ) -> str:
        """Open or add to a position. Returns position ID.

        cost_basis tracks price-only cost (no fees baked in) so that
        avg_entry_price stays clean. Fees are tracked separately via
        the cash balance deduction.
        """
        qty_d = _to_d(quantity)
        price_d = _to_d(price)
        fee_d = _to_d(fee)

        price_cost = qty_d * price_d  # Cost without fees
        cash_outflow = price_cost + fee_d  # Total cash spent

        # Lock prevents concurrent open_position calls from creating
        # duplicate positions for the same market/side
        async with self._position_lock:
            return await self._open_position_inner(
                market_id, token_id, side, qty_d, price_d, fee_d,
                price_cost, cash_outflow, ctx,
            )

    async def _open_position_inner(
        self,
        market_id: str,
        token_id: str,
        side: str,
        qty_d: Decimal,
        price_d: Decimal,
        fee_d: Decimal,
        price_cost: Decimal,
        cash_outflow: Decimal,
        ctx: TradingContext,
    ) -> str:
        """Inner position opening logic, called under _position_lock."""
        # Check if we already have a position in this market/side
        existing = await self._find_existing_position(market_id, side, ctx)

        if existing:
            # Scale in: update cost basis (fee-free)
            old_qty = _to_d(existing.quantity)
            old_cost = _to_d(existing.cost_basis)
            new_qty = old_qty + qty_d
            new_cost = old_cost + price_cost
            new_avg = new_cost / new_qty if new_qty > _ZERO else price_d

            await ctx.repo.update_position(existing.id, {
                "quantity": new_qty,
                "cost_basis": new_cost,
                "avg_entry_price": new_avg,
                "current_price": price_d,
            })

            self._cash_balance -= cash_outflow
            logger.info(
                f"Scaled into position {existing.id}: "
                f"+{qty_d:.4f} @ {price_d:.4f} (avg={new_avg:.4f})"
            )
            return existing.id
        else:
            # New position
            position_id = str(uuid.uuid4())
            await ctx.repo.create_position({
                "id": position_id,
                "market_id": market_id,
                "token_id": token_id,
                "side": side,
                "quantity": qty_d,
                "cost_basis": price_cost,
                "avg_entry_price": price_d,
                "current_price": price_d,
                "unrealized_pnl": _ZERO,
                "realized_pnl": _ZERO,
                "status": "open",
            })

            self._cash_balance -= cash_outflow
            logger.info(
                f"Opened position {position_id}: "
                f"{side} {qty_d:.4f} @ {price_d:.4f}"
            )
            return position_id

    async def close_position(
        self,
        position_id: str,
        exit_price: float | Decimal,
        quantity: float | Decimal | None,
        fee: float | Decimal,
        ctx: TradingContext,
    ) -> Decimal:
        """Close or partially close a position. Returns realized PnL.

        Cash proceeds and PnL are computed consistently for both YES and NO:
        - YES: bought at avg_entry, selling at exit_price
        - NO: bought at avg_entry, selling at exit_price (NO token price)
        In both cases, proceeds = close_qty * exit_price.
        PnL = proceeds - cost_of_closed_portion - fee.
        """
        position = await ctx.repo.get_position(position_id)
        if not position:
            logger.warning(f"Position {position_id} not found")
            return _ZERO

        exit_d = _to_d(exit_price)
        fee_d = _to_d(fee)
        pos_qty = _to_d(position.quantity)
        close_qty = _to_d(quantity) if quantity is not None else pos_qty

        # Cost of the portion being closed (proportional to cost_basis)
        close_ratio = close_qty / pos_qty
        closed_cost = _to_d(position.cost_basis) * close_ratio

        # Proceeds from selling tokens at exit_price
        gross_proceeds = close_qty * exit_d
        net_proceeds = gross_proceeds - fee_d

        # PnL = what we got back minus what we paid
        pnl = net_proceeds - closed_cost

        self._cash_balance += net_proceeds
        self._realized_pnl += pnl

        remaining_qty = pos_qty - close_qty
        now = datetime.now(timezone.utc)
        if remaining_qty <= _DUST:  # Fully closed
            await ctx.repo.update_position(position_id, {
                "quantity": _ZERO,
                "status": "closed",
                "realized_pnl": _to_d(position.realized_pnl) + pnl,
                "closed_at": now,
            })
            logger.info(
                f"Closed position {position_id}: pnl={pnl:+.4f}"
            )
        else:
            # Partial close — adjust cost basis proportionally
            remaining_cost = _to_d(position.cost_basis) - closed_cost
            await ctx.repo.update_position(position_id, {
                "quantity": remaining_qty,
                "cost_basis": remaining_cost,
                "realized_pnl": _to_d(position.realized_pnl) + pnl,
            })
            logger.info(
                f"Partially closed {position_id}: "
                f"-{close_qty:.4f}, remaining={remaining_qty:.4f}, pnl={pnl:+.4f}"
            )

        return pnl

    async def resolve_position(
        self,
        position_id: str,
        outcome: int,
        ctx: TradingContext,
    ) -> Decimal:
        """Resolve a position when market settles (outcome: 1=YES, 0=NO)."""
        position = await ctx.repo.get_position(position_id)
        if not position:
            return _ZERO

        # Settlement: YES tokens pay 1.0 if YES wins, 0.0 if NO wins
        settlement_price = _ONE if outcome == 1 else _ZERO
        if position.side == "NO":
            settlement_price = _ONE - settlement_price

        qty = _to_d(position.quantity)
        proceeds = qty * settlement_price
        pnl = proceeds - _to_d(position.cost_basis)
        self._cash_balance += proceeds
        self._realized_pnl += pnl

        await ctx.repo.update_position(position_id, {
            "status": "resolved",
            "realized_pnl": pnl,
            "current_price": settlement_price,
            "closed_at": datetime.now(timezone.utc),
        })

        return pnl

    async def get_summary(self, ctx: TradingContext) -> PortfolioSummary:
        """Get current portfolio summary."""
        positions = await ctx.repo.get_open_positions()

        positions_value = sum(
            (_to_d(p.quantity) * _to_d(p.current_price) for p in positions),
            _ZERO,
        )
        unrealized = sum(
            (_to_d(p.unrealized_pnl) for p in positions),
            _ZERO,
        )
        total = self._cash_balance + positions_value

        # Update metrics (Prometheus accepts float)
        PORTFOLIO_VALUE.set(float(total))
        OPEN_POSITIONS.set(len(positions))
        UNREALIZED_PNL.set(float(unrealized))
        REALIZED_PNL.set(float(self._realized_pnl))

        return PortfolioSummary(
            total_value=total.quantize(Decimal("0.01")),
            cash_balance=self._cash_balance.quantize(Decimal("0.01")),
            positions_value=positions_value.quantize(Decimal("0.01")),
            unrealized_pnl=unrealized.quantize(Decimal("0.01")),
            realized_pnl=self._realized_pnl.quantize(Decimal("0.01")),
            open_positions_count=len(positions),
        )

    async def save_snapshot(self, ctx: TradingContext) -> None:
        """Save a portfolio snapshot to the database."""
        summary = await self.get_summary(ctx)
        await ctx.repo.save_portfolio_snapshot({
            "total_value": summary.total_value,
            "cash_balance": summary.cash_balance,
            "positions_value": summary.positions_value,
            "unrealized_pnl": summary.unrealized_pnl,
            "realized_pnl": summary.realized_pnl,
            "open_positions_count": summary.open_positions_count,
        })

    async def update_prices(self, ctx: TradingContext) -> None:
        """Update current prices and unrealized PnL for all open positions."""
        positions = await ctx.repo.get_open_positions()
        if not positions or not ctx.clob:
            return

        async def _update_one(pos):  # noqa: ANN001
            try:
                price = await ctx.clob.get_price(pos.token_id, "buy")
                if price <= 0:
                    logger.warning(f"Invalid price {price} for {pos.token_id}, skipping update")
                    return
                price_d = _to_d(price)
                avg_entry = _to_d(pos.avg_entry_price)
                qty = _to_d(pos.quantity)
                unrealized = (price_d - avg_entry) * qty
                if pos.side == "NO":
                    unrealized = (avg_entry - price_d) * qty
                await ctx.repo.update_position(pos.id, {
                    "current_price": price_d,
                    "unrealized_pnl": unrealized,
                })
            except Exception as e:
                logger.warning(f"Price update failed for {pos.id}: {e}")

        await asyncio.gather(*[_update_one(p) for p in positions])

    async def _find_existing_position(
        self, market_id: str, side: str, ctx: TradingContext
    ) -> object | None:
        """Find an existing open position for the same market/side."""
        positions = await ctx.repo.get_open_positions()
        for p in positions:
            if p.market_id == market_id and p.side == side:
                return p
        return None
