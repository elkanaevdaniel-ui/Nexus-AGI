"""Portfolio and position API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.auth import TokenPayload, require_auth, require_operator
from src.api.dependencies import get_trading_context
from src.context import TradingContext
from src.data.schemas import PortfolioSummary, PositionResponse

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("/summary", response_model=PortfolioSummary)
async def get_portfolio_summary(
    _auth: TokenPayload = Depends(require_auth),
    ctx: TradingContext = Depends(get_trading_context),
) -> PortfolioSummary:
    """Get current portfolio summary."""
    portfolio = getattr(ctx, "portfolio", None)

    if portfolio:
        return await portfolio.get_summary(ctx)

    return PortfolioSummary(
        total_value=float(ctx.config.initial_bankroll),
        cash_balance=float(ctx.config.initial_bankroll),
        positions_value=0.0,
        unrealized_pnl=0.0,
        realized_pnl=0.0,
        open_positions_count=0,
    )


@router.post("/snapshot")
async def save_portfolio_snapshot(
    _auth: TokenPayload = Depends(require_operator),
    ctx: TradingContext = Depends(get_trading_context),
) -> dict:
    """Save a portfolio snapshot."""
    portfolio = getattr(ctx, "portfolio", None)

    if portfolio:
        await portfolio.save_snapshot(ctx)
        return {"status": "saved"}

    return {"status": "no_portfolio_tracker"}


@router.get("/positions", response_model=list[PositionResponse])
async def get_positions(
    _auth: TokenPayload = Depends(require_auth),
    ctx: TradingContext = Depends(get_trading_context),
) -> list[PositionResponse]:
    """Get all open positions."""
    positions = await ctx.repo.get_open_positions()

    return [
        PositionResponse(
            id=p.id,
            market_id=p.market_id,
            side=p.side,
            quantity=p.quantity,
            avg_entry_price=p.avg_entry_price,
            current_price=p.current_price,
            unrealized_pnl=p.unrealized_pnl,
            realized_pnl=p.realized_pnl,
            status=p.status,
            opened_at=p.opened_at,
        )
        for p in positions
    ]
