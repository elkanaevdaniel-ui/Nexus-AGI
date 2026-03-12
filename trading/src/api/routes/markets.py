"""Market data API endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from src.api.auth import TokenPayload, require_auth
from src.api.dependencies import get_trading_context
from src.context import TradingContext
from pydantic import BaseModel

router = APIRouter(prefix="/api/markets", tags=["markets"])


class MarketResponse(BaseModel):
    """Market data for API response."""

    id: str
    question: str
    category: str
    volume: float
    liquidity: float
    current_price_yes: float
    current_price_no: float
    active: bool


@router.get("/", response_model=list[MarketResponse])
async def list_markets(
    active: bool = True,
    limit: int = Query(50, ge=1, le=200),
    _auth: TokenPayload = Depends(require_auth),
    ctx: TradingContext = Depends(get_trading_context),
) -> list[MarketResponse]:
    """List tracked markets."""
    markets = await ctx.repo.get_active_markets()

    return [
        MarketResponse(
            id=m.id,
            question=m.question,
            category=m.category,
            volume=m.volume,
            liquidity=m.liquidity,
            current_price_yes=m.current_price_yes,
            current_price_no=m.current_price_no,
            active=m.active,
        )
        for m in markets[:limit]
    ]


@router.get("/{market_id}", response_model=Optional[MarketResponse])
async def get_market(
    market_id: str = Path(..., max_length=128, pattern=r"^[a-zA-Z0-9_\-]+$"),
    _auth: TokenPayload = Depends(require_auth),
    ctx: TradingContext = Depends(get_trading_context),
) -> MarketResponse:
    """Get a specific market."""
    market = await ctx.repo.get_market(market_id)

    if not market:
        raise HTTPException(status_code=404, detail="Market not found")

    return MarketResponse(
        id=market.id,
        question=market.question,
        category=market.category,
        volume=market.volume,
        liquidity=market.liquidity,
        current_price_yes=market.current_price_yes,
        current_price_no=market.current_price_no,
        active=market.active,
    )
