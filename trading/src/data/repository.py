"""Data access layer using the repository pattern."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.data import models


def _new_id() -> str:
    """Generate a new UUID string."""
    return str(uuid.uuid4())


class Repository:
    """Central data access layer for all database operations."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    # --- Markets ---

    async def upsert_market(self, market_data: dict) -> models.Market:
        """Insert or update a market record."""
        async with self._session_factory() as session:
            existing = await session.get(models.Market, market_data["id"])
            if existing:
                for key, value in market_data.items():
                    if key != "id":
                        setattr(existing, key, value)
                existing.updated_at = datetime.now(timezone.utc)
                await session.commit()
                await session.refresh(existing)
                return existing
            market = models.Market(**market_data)
            session.add(market)
            await session.commit()
            await session.refresh(market)
            return market

    async def get_market(self, market_id: str) -> Optional[models.Market]:
        """Get a market by ID."""
        async with self._session_factory() as session:
            return await session.get(models.Market, market_id)

    async def get_active_markets(self) -> list[models.Market]:
        """Get all active markets."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(models.Market)
                .where(models.Market.active.is_(True))
                .order_by(models.Market.volume.desc())
            )
            return list(result.scalars().all())

    # --- Positions ---

    async def create_position(self, position_data: dict) -> models.Position:
        """Create a new position."""
        async with self._session_factory() as session:
            if "id" not in position_data:
                position_data["id"] = _new_id()
            position = models.Position(**position_data)
            session.add(position)
            await session.commit()
            await session.refresh(position)
            return position

    async def get_open_positions(self) -> list[models.Position]:
        """Get all open positions."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(models.Position).where(
                    models.Position.status == "open"
                )
            )
            return list(result.scalars().all())

    async def get_position(self, position_id: str) -> Optional[models.Position]:
        """Get a position by ID."""
        async with self._session_factory() as session:
            return await session.get(models.Position, position_id)

    async def update_position(
        self, position_id: str, updates: dict
    ) -> Optional[models.Position]:
        """Update a position by ID."""
        async with self._session_factory() as session:
            position = await session.get(models.Position, position_id)
            if not position:
                return None
            for key, value in updates.items():
                setattr(position, key, value)
            position.updated_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(position)
            return position

    # --- Orders ---

    async def create_order(self, order_data: dict) -> models.Order:
        """Create a new order record."""
        async with self._session_factory() as session:
            if "id" not in order_data:
                order_data["id"] = _new_id()
            order = models.Order(**order_data)
            session.add(order)
            await session.commit()
            await session.refresh(order)
            return order

    async def update_order_status(
        self, order_id: str, status: str, **kwargs: object
    ) -> None:
        """Update order status and optional fields."""
        async with self._session_factory() as session:
            values = {"status": status, "updated_at": datetime.now(timezone.utc)}
            values.update(kwargs)
            await session.execute(
                update(models.Order)
                .where(models.Order.id == order_id)
                .values(**values)
            )
            await session.commit()

    # --- Trades ---

    async def record_trade(self, trade_data: dict) -> models.Trade:
        """Record a trade fill."""
        async with self._session_factory() as session:
            if "id" not in trade_data:
                trade_data["id"] = _new_id()
            trade = models.Trade(**trade_data)
            session.add(trade)
            await session.commit()
            await session.refresh(trade)
            return trade

    async def get_trades_for_market(
        self, market_id: str
    ) -> list[models.Trade]:
        """Get all trades for a given market."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(models.Trade)
                .where(models.Trade.market_id == market_id)
                .order_by(models.Trade.executed_at.desc())
            )
            return list(result.scalars().all())

    async def get_recent_trades(self, limit: int = 50) -> list[models.Trade]:
        """Get the most recent trades across all markets."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(models.Trade)
                .order_by(models.Trade.executed_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())

    # --- Probability Estimates ---

    async def save_probability_estimate(
        self, estimate_data: dict
    ) -> models.ProbabilityEstimate:
        """Save a probability estimate."""
        async with self._session_factory() as session:
            if "id" not in estimate_data:
                estimate_data["id"] = _new_id()
            estimate = models.ProbabilityEstimate(**estimate_data)
            session.add(estimate)
            await session.commit()
            await session.refresh(estimate)
            return estimate

    async def get_estimates_for_market(
        self, market_id: str
    ) -> list[models.ProbabilityEstimate]:
        """Get all probability estimates for a market."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(models.ProbabilityEstimate)
                .where(models.ProbabilityEstimate.market_id == market_id)
                .order_by(models.ProbabilityEstimate.created_at.desc())
            )
            return list(result.scalars().all())

    async def update_estimate_brier(
        self, estimate_id: str, brier_score: float
    ) -> None:
        """Update the Brier score for an estimate after market resolution."""
        async with self._session_factory() as session:
            await session.execute(
                update(models.ProbabilityEstimate)
                .where(models.ProbabilityEstimate.id == estimate_id)
                .values(brier_score=brier_score)
            )
            await session.commit()

    async def get_recent_brier_scores(
        self, limit: int = 100
    ) -> list[float]:
        """Get recent Brier scores for calibration tracking."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(models.ProbabilityEstimate.brier_score)
                .where(models.ProbabilityEstimate.brier_score.isnot(None))
                .order_by(models.ProbabilityEstimate.created_at.desc())
                .limit(limit)
            )
            return [row[0] for row in result.all()]

    # --- Portfolio Snapshots ---

    async def save_portfolio_snapshot(
        self, snapshot_data: dict
    ) -> models.PortfolioSnapshot:
        """Save a portfolio snapshot."""
        async with self._session_factory() as session:
            if "id" not in snapshot_data:
                snapshot_data["id"] = _new_id()
            snapshot = models.PortfolioSnapshot(**snapshot_data)
            session.add(snapshot)
            await session.commit()
            await session.refresh(snapshot)
            return snapshot

    async def get_latest_portfolio_snapshot(
        self,
    ) -> Optional[models.PortfolioSnapshot]:
        """Get the most recent portfolio snapshot."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(models.PortfolioSnapshot)
                .order_by(models.PortfolioSnapshot.created_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()

    # --- Alerts ---

    async def create_alert(self, alert_data: dict) -> models.Alert:
        """Create an alert."""
        async with self._session_factory() as session:
            if "id" not in alert_data:
                alert_data["id"] = _new_id()
            alert = models.Alert(**alert_data)
            session.add(alert)
            await session.commit()
            await session.refresh(alert)
            return alert

    # --- Reconciliation ---

    async def log_reconciliation_event(
        self, event_data: dict
    ) -> models.ReconciliationLog:
        """Log a reconciliation discrepancy."""
        async with self._session_factory() as session:
            if "id" not in event_data:
                event_data["id"] = _new_id()
            event = models.ReconciliationLog(**event_data)
            session.add(event)
            await session.commit()
            await session.refresh(event)
            return event

    # --- Circuit Breaker Events ---

    async def log_circuit_breaker(
        self, event_data: dict
    ) -> models.CircuitBreakerEvent:
        """Log a circuit breaker activation."""
        async with self._session_factory() as session:
            if "id" not in event_data:
                event_data["id"] = _new_id()
            event = models.CircuitBreakerEvent(**event_data)
            session.add(event)
            await session.commit()
            await session.refresh(event)
            return event

    # --- Market Resolutions ---

    async def record_resolution(
        self, resolution_data: dict
    ) -> models.MarketResolution:
        """Record a market resolution."""
        async with self._session_factory() as session:
            if "id" not in resolution_data:
                resolution_data["id"] = _new_id()
            resolution = models.MarketResolution(**resolution_data)
            session.add(resolution)
            await session.commit()
            await session.refresh(resolution)
            return resolution

    # --- LLM Calls ---

    async def log_llm_call(self, call_data: dict) -> models.LLMCall:
        """Log an LLM API call for cost tracking."""
        async with self._session_factory() as session:
            if "id" not in call_data:
                call_data["id"] = _new_id()
            call = models.LLMCall(**call_data)
            session.add(call)
            await session.commit()
            await session.refresh(call)
            return call

    # --- Pending Trades ---

    async def create_pending_trade(
        self, trade_data: dict
    ) -> models.PendingTrade:
        """Create a pending trade awaiting user approval."""
        async with self._session_factory() as session:
            if "id" not in trade_data:
                trade_data["id"] = _new_id()
            pending = models.PendingTrade(**trade_data)
            session.add(pending)
            await session.commit()
            await session.refresh(pending)
            return pending

    async def get_pending_trades(self) -> list[models.PendingTrade]:
        """Get all pending trades awaiting approval."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(models.PendingTrade)
                .where(models.PendingTrade.status == "pending")
                .order_by(models.PendingTrade.created_at.desc())
            )
            return list(result.scalars().all())

    async def update_pending_trade_status(
        self, trade_id: str, status: str
    ) -> Optional[models.PendingTrade]:
        """Update a pending trade status (approved/rejected/expired)."""
        async with self._session_factory() as session:
            pending = await session.get(models.PendingTrade, trade_id)
            if not pending:
                return None
            pending.status = status
            pending.decided_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(pending)
            return pending

    async def get_pending_trade(
        self, trade_id: str
    ) -> Optional[models.PendingTrade]:
        """Get a pending trade by ID."""
        async with self._session_factory() as session:
            return await session.get(models.PendingTrade, trade_id)

    async def expire_old_pending_trades(
        self, max_age_hours: int = 2
    ) -> int:
        """Expire pending trades older than max_age_hours. Returns count expired."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        async with self._session_factory() as session:
            result = await session.execute(
                update(models.PendingTrade)
                .where(
                    models.PendingTrade.status == "pending",
                    models.PendingTrade.created_at < cutoff,
                )
                .values(
                    status="expired",
                    decided_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()
            return result.rowcount  # type: ignore[return-value]

    # --- Order Events ---

    async def log_order_event(self, event_data: dict) -> models.OrderEvent:
        """Log an order lifecycle event."""
        async with self._session_factory() as session:
            if "id" not in event_data:
                event_data["id"] = _new_id()
            event = models.OrderEvent(**event_data)
            session.add(event)
            await session.commit()
            await session.refresh(event)
            return event
