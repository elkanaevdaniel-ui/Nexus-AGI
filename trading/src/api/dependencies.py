"""FastAPI dependency injection helpers."""

from __future__ import annotations

from fastapi import Request

from src.context import TradingContext


def get_trading_context(request: Request) -> TradingContext:
    """Get the TradingContext from app state."""
    return request.app.state.trading_ctx
