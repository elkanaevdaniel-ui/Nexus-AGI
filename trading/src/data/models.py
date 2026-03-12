"""SQLAlchemy ORM models — 12 tables for the trading system."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from decimal import Decimal

from sqlalchemy import (
    DateTime,
    Float,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Monetary precision: 18 digits total, 8 decimal places
_MONEY = Numeric(18, 8)


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class Market(Base):
    """Tracked markets from Gamma API."""

    __tablename__ = "markets"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    condition_id: Mapped[str] = mapped_column(String(255), index=True)
    question: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(100), default="", index=True)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    volume: Mapped[float] = mapped_column(Float, default=0.0)
    liquidity: Mapped[float] = mapped_column(Float, default=0.0)
    outcome_yes_token: Mapped[str] = mapped_column(String(255), default="")
    outcome_no_token: Mapped[str] = mapped_column(String(255), default="")
    current_price_yes: Mapped[float] = mapped_column(Float, default=0.5)
    current_price_no: Mapped[float] = mapped_column(Float, default=0.5)
    neg_risk: Mapped[bool] = mapped_column(default=False)
    active: Mapped[bool] = mapped_column(default=True, index=True)
    fee_rate_bps: Mapped[int] = mapped_column(Integer, default=200)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_markets_volume", "volume"),
        Index("ix_markets_active_volume", "active", "volume"),
    )


class Position(Base):
    """Open and closed trading positions."""

    __tablename__ = "positions"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    market_id: Mapped[str] = mapped_column(String(255), index=True)
    token_id: Mapped[str] = mapped_column(String(255))
    side: Mapped[str] = mapped_column(String(10))  # YES or NO
    quantity: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal(0))
    cost_basis: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal(0))
    avg_entry_price: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal(0))
    current_price: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal(0))
    unrealized_pnl: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal(0))
    realized_pnl: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal(0))
    status: Mapped[str] = mapped_column(
        String(20), default="open", index=True
    )  # open, closed, resolved
    opened_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_positions_market_status", "market_id", "status"),
    )


class Order(Base):
    """Order records for placed orders."""

    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    market_id: Mapped[str] = mapped_column(String(255), index=True)
    position_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    token_id: Mapped[str] = mapped_column(String(255))
    side: Mapped[str] = mapped_column(String(10))  # BUY or SELL
    price: Mapped[Decimal] = mapped_column(_MONEY)
    size: Mapped[Decimal] = mapped_column(_MONEY)
    filled_size: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal(0))
    order_type: Mapped[str] = mapped_column(
        String(10), default="GTC"
    )  # GTC, GTD, FOK
    status: Mapped[str] = mapped_column(
        String(20), default="pending", index=True
    )  # pending, placed, partial, filled, cancelled, rejected
    clob_order_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    fee_paid: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal(0))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class Trade(Base):
    """Executed trade records (fills)."""

    __tablename__ = "trades"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(255), index=True)
    market_id: Mapped[str] = mapped_column(String(255), index=True)
    token_id: Mapped[str] = mapped_column(String(255))
    side: Mapped[str] = mapped_column(String(10))
    price: Mapped[Decimal] = mapped_column(_MONEY)
    size: Mapped[Decimal] = mapped_column(_MONEY)
    fee: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal(0))
    slippage: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal(0))
    is_paper: Mapped[bool] = mapped_column(default=True)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class ProbabilityEstimate(Base):
    """LLM probability estimates for calibration tracking."""

    __tablename__ = "probability_estimates"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    market_id: Mapped[str] = mapped_column(String(255), index=True)
    model: Mapped[str] = mapped_column(String(50))
    probability: Mapped[float] = mapped_column(Float)
    confidence: Mapped[str] = mapped_column(String(20))
    reasoning: Mapped[str] = mapped_column(Text, default="")
    market_price_at_estimate: Mapped[float] = mapped_column(Float, default=0.0)
    brier_score: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )  # Filled on resolution
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class PortfolioSnapshot(Base):
    """Periodic snapshots of portfolio state."""

    __tablename__ = "portfolio_snapshots"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    total_value: Mapped[Decimal] = mapped_column(_MONEY)
    cash_balance: Mapped[Decimal] = mapped_column(_MONEY)
    positions_value: Mapped[Decimal] = mapped_column(_MONEY)
    unrealized_pnl: Mapped[Decimal] = mapped_column(_MONEY)
    realized_pnl: Mapped[Decimal] = mapped_column(_MONEY)
    open_positions_count: Mapped[int] = mapped_column(Integer)
    daily_pnl: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal(0))
    max_drawdown: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal(0))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), index=True
    )


class Alert(Base):
    """System alerts and notifications."""

    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    alert_type: Mapped[str] = mapped_column(
        String(50), index=True
    )  # trade, risk, error, info
    severity: Mapped[str] = mapped_column(
        String(20), default="info"
    )  # info, warning, critical
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    acknowledged: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class MarketResolution(Base):
    """Track market resolutions and realized PnL."""

    __tablename__ = "market_resolutions"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    market_id: Mapped[str] = mapped_column(String(255), index=True, unique=True)
    outcome: Mapped[int] = mapped_column(Integer)  # 1=YES, 0=NO
    resolved_at: Mapped[datetime] = mapped_column(DateTime)
    realized_pnl: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal(0))
    position_size: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal(0))
    entry_price: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal(0))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class ReconciliationLog(Base):
    """Audit trail for state drift between DB and chain."""

    __tablename__ = "reconciliation_log"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    reconciliation_type: Mapped[str] = mapped_column(
        String(50)
    )  # position, order, balance
    market_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    db_value: Mapped[str] = mapped_column(Text, default="")
    chain_value: Mapped[str] = mapped_column(Text, default="")
    discrepancy: Mapped[str] = mapped_column(Text, default="")
    resolved: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class CircuitBreakerEvent(Base):
    """Every circuit breaker activation."""

    __tablename__ = "circuit_breaker_events"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    breaker_type: Mapped[str] = mapped_column(
        String(50), index=True
    )  # daily_loss, drawdown, position_limit, correlation
    trigger_value: Mapped[Decimal] = mapped_column(_MONEY)
    threshold: Mapped[Decimal] = mapped_column(_MONEY)
    action_taken: Mapped[str] = mapped_column(String(100))
    resolved: Mapped[bool] = mapped_column(default=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class OrderEvent(Base):
    """Full order lifecycle events."""

    __tablename__ = "order_events"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(255), index=True)
    event_type: Mapped[str] = mapped_column(
        String(30)
    )  # placed, partial_fill, filled, cancelled, rejected
    details: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class PendingTrade(Base):
    """Trades awaiting user approval before execution."""

    __tablename__ = "pending_trades"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    market_id: Mapped[str] = mapped_column(String(255), index=True)
    question: Mapped[str] = mapped_column(Text, default="")
    action: Mapped[str] = mapped_column(String(10))  # BUY or SELL
    token_id: Mapped[str] = mapped_column(String(255))
    size_usd: Mapped[Decimal] = mapped_column(_MONEY)
    price: Mapped[Decimal] = mapped_column(_MONEY)
    edge_magnitude: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal(0))
    estimated_prob: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal(0))
    market_price: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal(0))
    kelly_fraction: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal(0))
    confidence: Mapped[str] = mapped_column(String(20), default="medium")
    reasoning: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(
        String(20), default="pending", index=True
    )  # pending, approved, rejected, expired
    decided_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_pending_trades_status_created", "status", "created_at"),
    )


class LLMCall(Base):
    """LLM cost tracking, latency, and prompt hash."""

    __tablename__ = "llm_calls"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    model: Mapped[str] = mapped_column(String(50), index=True)
    market_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    prompt_hash: Mapped[str] = mapped_column(String(64), default="")
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(
        String(20), default="success"
    )  # success, error, timeout
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
