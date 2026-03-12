"""Pydantic request/response schemas for all API data."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

import json

from pydantic import BaseModel, Field, field_validator


def _parse_json_list(v: object) -> list[str]:
    """Parse a JSON-encoded list string into an actual list."""
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        try:
            parsed = json.loads(v)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        except (json.JSONDecodeError, TypeError):
            pass
    return []


# --- Gamma API response schemas ---


class GammaMarket(BaseModel):
    """Market data from Gamma API (untrusted external data).

    The Gamma API returns camelCase field names. We use aliases to map them
    to snake_case Python attributes. populate_by_name=True allows both forms.
    """

    id: str
    condition_id: str = Field("", alias="conditionId")
    question: str = ""
    description: str = ""
    category: str = ""
    end_date_iso: Optional[str] = Field(None, alias="endDate")
    volume: float = 0.0
    liquidity: float = 0.0
    outcomes: list[str] = Field(default_factory=list)
    outcome_prices: list[str] = Field(default_factory=list, alias="outcomePrices")
    clob_token_ids: list[str] = Field(default_factory=list, alias="clobTokenIds")
    neg_risk: bool = Field(False, alias="negRisk")
    active: bool = True

    model_config = {"populate_by_name": True}

    @field_validator("outcomes", "outcome_prices", "clob_token_ids", mode="before")
    @classmethod
    def parse_json_strings(cls, v: object) -> list[str]:
        return _parse_json_list(v)


# --- CLOB API schemas ---


class OrderBookLevel(BaseModel):
    """Single price level in the order book."""

    price: str
    size: str


class OrderBookSummary(BaseModel):
    """Order book snapshot from CLOB API."""

    market: str = ""
    asset_id: str = ""
    bids: list[OrderBookLevel] = Field(default_factory=list)
    asks: list[OrderBookLevel] = Field(default_factory=list)
    hash: str = ""
    timestamp: str = ""


# --- LLM probability schemas ---


class ProbabilityFactor(BaseModel):
    """A factor influencing probability estimate."""

    factor: str
    direction: Literal["up", "down"]
    magnitude: Literal["small", "medium", "large"]


class LLMProbabilityEstimate(BaseModel):
    """Validated LLM probability output. Clamped to [0.01, 0.99]."""

    probability: float = Field(ge=0.01, le=0.99)
    confidence: Literal["low", "medium", "high"]
    base_rate: float = Field(ge=0.0, le=1.0)
    factors: list[ProbabilityFactor] = Field(default_factory=list)
    reasoning: str = ""


class ConsensusEstimate(BaseModel):
    """Multi-LLM consensus probability."""

    probability: float = Field(ge=0.01, le=0.99)
    confidence: Literal["low", "medium", "high"]
    claude_estimate: Optional[float] = None
    gemini_estimate: Optional[float] = None
    gpt_estimate: Optional[float] = None
    openrouter_estimate: Optional[float] = None
    spread: float = 0.0  # Max - min across models
    reasoning: str = ""


# --- Trading decision schemas ---


class EdgeResult(BaseModel):
    """Edge calculation result."""

    magnitude: Decimal  # Absolute edge after fees
    direction: Literal["BUY", "SELL"]
    estimated_prob: Decimal
    market_price: Decimal
    fee_pct: Decimal
    raw_edge: Decimal  # Before fees


class KellyResult(BaseModel):
    """Kelly criterion sizing result."""

    fraction: Decimal  # Raw Kelly fraction
    adjusted_fraction: Decimal  # After fractional multiplier
    position_size_usd: Decimal
    edge_after_fees: Decimal
    expected_value: Decimal  # EV per dollar bet


class TradeDecision(BaseModel):
    """Final decision for a market evaluation."""

    action: Literal["BUY", "SELL", "SKIP"]
    reason: str = ""
    market_id: str = ""
    token_id: str = ""
    size_usd: Decimal = Decimal(0)
    price: Decimal = Decimal(0)
    edge: Optional[EdgeResult] = None
    kelly: Optional[KellyResult] = None
    estimate: Optional[ConsensusEstimate] = None


# --- Risk schemas ---


class RiskCheckResult(BaseModel):
    """Result of risk manager check."""

    approved: bool
    reason: str = ""
    breaker_type: Optional[str] = None


# --- Portfolio schemas ---


class PortfolioSummary(BaseModel):
    """Current portfolio state summary."""

    total_value: Decimal
    cash_balance: Decimal
    positions_value: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal
    open_positions_count: int
    daily_pnl: Decimal = Decimal(0)
    max_drawdown: Decimal = Decimal(0)
    win_rate: Decimal = Decimal(0)
    sharpe_ratio: Decimal = Decimal(0)


class PositionResponse(BaseModel):
    """Position data for API responses."""

    id: str
    market_id: str
    side: str
    quantity: Decimal
    avg_entry_price: Decimal
    current_price: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal
    status: str
    opened_at: datetime


# --- API request/response schemas ---


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"
    trading_mode: str
    trading_paused: bool
    uptime_seconds: float
    version: str = "1.0.0"


class DynamicConfigUpdate(BaseModel):
    """Partial update for dynamic config."""

    kelly_fraction: Optional[float] = Field(None, ge=0.05, le=1.0)
    min_edge_threshold: Optional[float] = Field(None, ge=0.02, le=0.20)
    max_daily_loss_pct: Optional[float] = Field(None, ge=0.01, le=1.0)
    max_drawdown_pct: Optional[float] = Field(None, ge=0.05, le=1.0)
    max_single_position_pct: Optional[float] = Field(None, ge=0.01, le=0.50)
    max_open_positions: Optional[int] = Field(None, ge=1, le=50)
    scan_interval_seconds: Optional[int] = Field(None, ge=60, le=7200)


class CalibrationResponse(BaseModel):
    """Calibration metrics response."""

    rolling_brier_score: float
    total_resolved: int
    total_estimates: int
    brier_by_model: dict[str, float] = Field(default_factory=dict)


class ReconciliationEvent(BaseModel):
    """A reconciliation discrepancy."""

    reconciliation_type: str
    market_id: Optional[str] = None
    db_value: str
    chain_value: str
    discrepancy: str
