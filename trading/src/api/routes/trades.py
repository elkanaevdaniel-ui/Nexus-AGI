"""Trade history and pending trade approval API endpoints."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from pydantic import BaseModel

from src.api.auth import TokenPayload, require_auth, require_operator
from src.api.dependencies import get_trading_context
from src.context import TradingContext
from src.data.schemas import TradeDecision

router = APIRouter(prefix="/api/trades", tags=["trades"])


class TradeResponse(BaseModel):
    """Trade data for API response."""

    id: str
    order_id: str
    market_id: str
    side: str
    price: float
    size: float
    fee: float
    slippage: float
    is_paper: bool
    executed_at: datetime


class PendingTradeResponse(BaseModel):
    """Pending trade awaiting user approval."""

    id: str
    market_id: str
    question: str
    action: str
    size_usd: float
    price: float
    edge_magnitude: float
    estimated_prob: float
    market_price: float
    kelly_fraction: float
    confidence: str
    reasoning: str
    status: str
    created_at: datetime


@router.get("/", response_model=list[TradeResponse])
async def list_trades(
    market_id: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    _auth: TokenPayload = Depends(require_auth),
    ctx: TradingContext = Depends(get_trading_context),
) -> list[TradeResponse]:
    """List recent trades, optionally filtered by market."""
    if market_id:
        trades = await ctx.repo.get_trades_for_market(market_id)
    else:
        trades = await ctx.repo.get_recent_trades(limit=limit)

    return [
        TradeResponse(
            id=t.id,
            order_id=t.order_id,
            market_id=t.market_id,
            side=t.side,
            price=t.price,
            size=t.size,
            fee=t.fee,
            slippage=t.slippage,
            is_paper=t.is_paper,
            executed_at=t.executed_at,
        )
        for t in trades[:limit]
    ]


@router.get("/pending", response_model=list[PendingTradeResponse])
async def list_pending_trades(
    _auth: TokenPayload = Depends(require_auth),
    ctx: TradingContext = Depends(get_trading_context),
) -> list[PendingTradeResponse]:
    """List all trades awaiting user approval."""
    pending = await ctx.repo.get_pending_trades()
    return [
        PendingTradeResponse(
            id=p.id,
            market_id=p.market_id,
            question=p.question,
            action=p.action,
            size_usd=float(p.size_usd),
            price=float(p.price),
            edge_magnitude=float(p.edge_magnitude),
            estimated_prob=float(p.estimated_prob),
            market_price=float(p.market_price),
            kelly_fraction=float(p.kelly_fraction),
            confidence=p.confidence,
            reasoning=p.reasoning,
            status=p.status,
            created_at=p.created_at,
        )
        for p in pending
    ]


@router.post("/approve/{trade_id}")
async def approve_trade(
    trade_id: str,
    _auth: TokenPayload = Depends(require_operator),
    ctx: TradingContext = Depends(get_trading_context),
) -> dict:
    """Approve a pending trade for execution."""
    from src.core.pipeline import execute_decision

    pending = await ctx.repo.get_pending_trade(trade_id)
    if not pending:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pending trade {trade_id} not found",
        )
    if pending.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Trade already {pending.status}",
        )

    # Mark as approved
    await ctx.repo.update_pending_trade_status(trade_id, "approved")

    # Build a TradeDecision and execute it
    decision = TradeDecision(
        action=pending.action,
        reason=f"User-approved pending trade {trade_id}",
        market_id=pending.market_id,
        token_id=pending.token_id,
        size_usd=pending.size_usd,
        price=pending.price,
    )

    result = await execute_decision(decision, ctx)
    logger.info(f"Approved trade {trade_id} executed: {result.get('status')}")
    return {"trade_id": trade_id, "status": "approved", "execution": result}


@router.post("/reject/{trade_id}")
async def reject_trade(
    trade_id: str,
    _auth: TokenPayload = Depends(require_operator),
    ctx: TradingContext = Depends(get_trading_context),
) -> dict:
    """Reject a pending trade."""
    pending = await ctx.repo.get_pending_trade(trade_id)
    if not pending:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pending trade {trade_id} not found",
        )
    if pending.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Trade already {pending.status}",
        )

    await ctx.repo.update_pending_trade_status(trade_id, "rejected")
    logger.info(f"Rejected trade {trade_id}: {pending.question[:50]}")
    return {"trade_id": trade_id, "status": "rejected"}
