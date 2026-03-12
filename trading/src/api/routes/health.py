"""Health check endpoint — unauthenticated."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.dependencies import get_trading_context
from src.context import TradingContext
from src.data.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(
    ctx: TradingContext = Depends(get_trading_context),
) -> HealthResponse:
    """Health check endpoint. No authentication required."""
    return HealthResponse(
        status="ok",
        trading_mode=ctx.config.trading_mode,
        trading_paused=ctx.trading_paused,
        uptime_seconds=ctx.uptime_seconds,
    )
