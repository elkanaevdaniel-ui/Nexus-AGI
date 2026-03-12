"""Prometheus metrics definitions."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# Trading metrics
TRADES_TOTAL = Counter(
    "trades_total",
    "Total number of trades placed",
    ["side", "status"],
)
TRADE_SIZE_USD = Histogram(
    "trade_size_usd",
    "Trade size in USD",
    buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000],
)

# Portfolio metrics
PORTFOLIO_VALUE = Gauge("portfolio_value_usd", "Total portfolio value in USD")
OPEN_POSITIONS = Gauge("open_positions_count", "Number of open positions")
UNREALIZED_PNL = Gauge("unrealized_pnl_usd", "Total unrealized PnL in USD")
REALIZED_PNL = Gauge("realized_pnl_usd", "Total realized PnL in USD")

# Risk metrics
DAILY_LOSS_PCT = Gauge("daily_loss_pct", "Daily loss as percentage of portfolio")
MAX_DRAWDOWN_PCT = Gauge("max_drawdown_pct", "Maximum drawdown percentage")
CIRCUIT_BREAKER_TRIPS = Counter(
    "circuit_breaker_trips_total",
    "Circuit breaker activations",
    ["reason"],
)

# Market scanning
MARKETS_SCANNED = Counter("markets_scanned_total", "Markets scanned per cycle")
MARKETS_WITH_EDGE = Gauge("markets_with_edge", "Markets with positive edge in last scan")

# LLM metrics
LLM_CALLS = Counter("llm_calls_total", "LLM API calls", ["model", "status"])
LLM_LATENCY = Histogram(
    "llm_latency_seconds",
    "LLM call latency",
    ["model"],
    buckets=[0.5, 1, 2, 5, 10, 30],
)
LLM_COST_USD = Counter("llm_cost_usd_total", "LLM API cost in USD", ["model"])

# Calibration
BRIER_SCORE = Gauge("brier_score_rolling", "Rolling Brier score (lower is better)")

# API metrics
API_CALLS = Counter("api_calls_total", "External API calls", ["service", "status"])
API_LATENCY = Histogram(
    "api_latency_seconds",
    "External API call latency",
    ["service"],
)

# Reconciliation
RECONCILIATION_DISCREPANCIES = Counter(
    "reconciliation_discrepancies_total",
    "Position discrepancies found during reconciliation",
)
