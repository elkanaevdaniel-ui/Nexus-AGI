"""Shared types for all signal sources."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Signal(BaseModel):
    """A single signal from any external source."""

    source: Literal["reddit", "twitter", "news", "search", "trends"]
    title: str
    body: str = ""
    url: str = ""
    published_at: datetime
    sentiment: float = Field(0.0, ge=-1.0, le=1.0)  # -1 bearish → +1 bullish
    relevance: float = Field(0.0, ge=0.0, le=1.0)
    metadata: dict = Field(default_factory=dict)


class MarketSignals(BaseModel):
    """Aggregated signals for a specific market question."""

    market_id: str
    question: str
    signals: list[Signal] = Field(default_factory=list)
    overall_sentiment: float = 0.0  # Weighted average
    signal_count: int = 0
    bullish_count: int = 0
    bearish_count: int = 0
    summary: str = ""  # LLM-generated summary of signals
