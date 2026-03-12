"""Control endpoints — pause/resume/close/config (elevated auth required)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.api.auth import TokenPayload, require_auth, require_operator
from src.api.dependencies import get_trading_context
from src.context import TradingContext
from src.data.schemas import DynamicConfigUpdate

router = APIRouter(prefix="/api/controls", tags=["controls"])


class TradingStateResponse(BaseModel):
    """Current trading state."""

    trading_paused: bool
    trading_mode: str
    circuit_breakers: list[str]


class PauseResumeRequest(BaseModel):
    """Request to pause or resume trading."""

    action: str  # "pause" or "resume"
    reason: str = ""


@router.get("/state", response_model=TradingStateResponse)
async def get_trading_state(
    _auth: TokenPayload = Depends(require_auth),
    ctx: TradingContext = Depends(get_trading_context),
) -> TradingStateResponse:
    """Get current trading state."""
    risk = getattr(ctx, "risk_manager", None)

    return TradingStateResponse(
        trading_paused=ctx.trading_paused,
        trading_mode=ctx.config.trading_mode,
        circuit_breakers=list(risk.tripped_breakers) if risk else [],
    )


@router.post("/trading", response_model=TradingStateResponse)
async def control_trading(
    body: PauseResumeRequest,
    _auth: TokenPayload = Depends(require_operator),
    ctx: TradingContext = Depends(get_trading_context),
) -> TradingStateResponse:
    """Pause or resume trading (operator+ auth required)."""
    if body.action == "pause":
        ctx.trading_paused = True
    elif body.action == "resume":
        risk = getattr(ctx, "risk_manager", None)
        if risk and risk.is_any_breaker_tripped:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot resume: circuit breakers active: {risk.tripped_breakers}",
            )
        ctx.trading_paused = False
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="action must be 'pause' or 'resume'",
        )

    risk = getattr(ctx, "risk_manager", None)
    return TradingStateResponse(
        trading_paused=ctx.trading_paused,
        trading_mode=ctx.config.trading_mode,
        circuit_breakers=list(risk.tripped_breakers) if risk else [],
    )


@router.patch("/config")
async def update_config(
    updates: DynamicConfigUpdate,
    _auth: TokenPayload = Depends(require_operator),
    ctx: TradingContext = Depends(get_trading_context),
) -> dict:
    """Update dynamic config with validated bounds (operator+ auth)."""
    changed: dict[str, object] = {}
    for field_name, value in updates.model_dump(exclude_none=True).items():
        old = getattr(ctx.dynamic_config, field_name)
        setattr(ctx.dynamic_config, field_name, value)
        changed[field_name] = {"old": old, "new": value}

    return {"updated": changed}


@router.post("/cancel-all")
async def cancel_all_orders(
    _auth: TokenPayload = Depends(require_operator),
    ctx: TradingContext = Depends(get_trading_context),
) -> dict:
    """Emergency: cancel all open orders (operator+ auth)."""
    if not ctx.clob:
        return {"status": "no_clob_client", "cancelled": 0}

    try:
        result = await ctx.clob.cancel_all()
        ctx.trading_paused = True
        return {"status": "cancelled", "result": result}
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Order cancellation failed",
        )
