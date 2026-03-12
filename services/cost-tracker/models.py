"""Pydantic models for the unified cost/budget tracking system."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class BudgetLevel(str, Enum):
    """Which budget level has been exceeded."""

    DAILY = "daily"
    MONTHLY = "monthly"
    PER_RUN = "per_run"
    SESSION = "session"


# ---------------------------------------------------------------------------
# Configuration (loaded from environment)
# ---------------------------------------------------------------------------

class BudgetConfig(BaseSettings):
    """Budget limits loaded from environment variables with sensible defaults.

    Environment variables:
        DAILY_BUDGET_USD   – default $5
        MONTHLY_BUDGET_USD – default $20
        PER_RUN_BUDGET_USD – default $1
        SESSION_CALL_LIMIT – default 5  (polymarket-style session cap)
        COST_DB_PATH       – default "costs.db"
    """

    daily_budget_usd: Decimal = Field(
        default=Decimal("5.00"),
        description="Maximum spend per calendar day (UTC).",
    )
    monthly_budget_usd: Decimal = Field(
        default=Decimal("20.00"),
        description="Maximum spend per calendar month (UTC).",
    )
    per_run_budget_usd: Decimal = Field(
        default=Decimal("1.00"),
        description="Maximum spend for a single run / task invocation.",
    )
    session_call_limit: int = Field(
        default=5,
        description="Maximum number of LLM calls per session.",
    )
    cost_db_path: str = Field(
        default="costs.db",
        description="Path to the SQLite database file.",
    )

    model_config = {"env_prefix": "", "case_sensitive": False}

    # Accept string representations of Decimal from env vars
    @field_validator(
        "daily_budget_usd",
        "monthly_budget_usd",
        "per_run_budget_usd",
        mode="before",
    )
    @classmethod
    def _coerce_decimal(cls, v: object) -> Decimal:
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))


# ---------------------------------------------------------------------------
# Core data models
# ---------------------------------------------------------------------------

class CostEntry(BaseModel):
    """A single LLM call cost record."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    provider: str = Field(
        ...,
        description="LLM provider name (e.g. 'openai', 'anthropic').",
    )
    model: str = Field(
        ...,
        description="Model identifier (e.g. 'gpt-4o', 'claude-sonnet-4-20250514').",
    )
    input_tokens: int = Field(..., ge=0)
    output_tokens: int = Field(..., ge=0)
    cost_usd: Decimal = Field(
        ...,
        description="Total cost of this call in USD.",
    )
    task_type: Optional[str] = Field(
        default=None,
        description="Optional label for the kind of task (e.g. 'research', 'trade').",
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Session identifier for session-level tracking.",
    )
    run_id: Optional[str] = Field(
        default=None,
        description="Run identifier for per-run budget tracking.",
    )

    @field_validator("cost_usd", mode="before")
    @classmethod
    def _coerce_cost(cls, v: object) -> Decimal:
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))

    model_config = {"frozen": True}


class BudgetStatus(BaseModel):
    """Snapshot of spend relative to every budget level."""

    daily_spend: Decimal = Decimal("0")
    daily_limit: Decimal = Decimal("5.00")
    daily_pct: Decimal = Decimal("0")
    daily_exceeded: bool = False

    monthly_spend: Decimal = Decimal("0")
    monthly_limit: Decimal = Decimal("20.00")
    monthly_pct: Decimal = Decimal("0")
    monthly_exceeded: bool = False

    per_run_spend: Decimal = Decimal("0")
    per_run_limit: Decimal = Decimal("1.00")
    per_run_pct: Decimal = Decimal("0")
    per_run_exceeded: bool = False

    session_call_count: int = 0
    session_call_limit: int = 5
    session_exceeded: bool = False

    @property
    def is_exceeded(self) -> bool:
        """Return True if *any* budget level is exceeded."""
        return (
            self.daily_exceeded
            or self.monthly_exceeded
            or self.per_run_exceeded
            or self.session_exceeded
        )

    @property
    def exceeded_levels(self) -> list[BudgetLevel]:
        """Return a list of all exceeded budget levels."""
        levels: list[BudgetLevel] = []
        if self.daily_exceeded:
            levels.append(BudgetLevel.DAILY)
        if self.monthly_exceeded:
            levels.append(BudgetLevel.MONTHLY)
        if self.per_run_exceeded:
            levels.append(BudgetLevel.PER_RUN)
        if self.session_exceeded:
            levels.append(BudgetLevel.SESSION)
        return levels


class SessionCost(BaseModel):
    """Aggregated cost information for a single session."""

    session_id: str
    total_cost: Decimal = Decimal("0")
    call_count: int = 0
    started_at: Optional[datetime] = None
    last_call_at: Optional[datetime] = None
