"""Calibration metrics API endpoints — Brier score, ECE, reliability data."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.auth import TokenPayload, require_auth
from src.api.dependencies import get_trading_context
from src.context import TradingContext
from src.data.schemas import CalibrationResponse

router = APIRouter(prefix="/api/calibration", tags=["calibration"])


@router.get("/", response_model=CalibrationResponse)
async def get_calibration(
    _auth: TokenPayload = Depends(require_auth),
    ctx: TradingContext = Depends(get_trading_context),
) -> CalibrationResponse:
    """Get calibration metrics (Brier score, ECE)."""
    scores = await ctx.repo.get_recent_brier_scores(100)
    rolling_brier = sum(scores) / len(scores) if scores else 0.25

    brier_by_model: dict[str, float] = {}
    for model_name in ["claude", "gemini", "gpt"]:
        pass

    return CalibrationResponse(
        rolling_brier_score=round(rolling_brier, 4),
        total_resolved=len(scores),
        total_estimates=len(scores),
        brier_by_model=brier_by_model,
    )
