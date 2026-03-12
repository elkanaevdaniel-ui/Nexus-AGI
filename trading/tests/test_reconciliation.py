"""Tests for state reconciliation."""

from __future__ import annotations

import pytest

from src.core.reconciliation import _is_stale_order, startup_reconciliation


class TestReconciliation:
    """Test reconciliation engine."""

    @pytest.mark.asyncio
    async def test_startup_reconciliation_paper(self, trading_ctx) -> None:
        """Paper mode should auto-resume after reconciliation."""
        trading_ctx.config.trading_mode = "paper"
        discrepancies = await startup_reconciliation(trading_ctx)
        assert isinstance(discrepancies, list)
        assert trading_ctx.trading_paused is False

    @pytest.mark.asyncio
    async def test_startup_reconciliation_live_pauses(self, trading_ctx) -> None:
        """Live mode should remain paused after reconciliation."""
        trading_ctx.config.trading_mode = "live"
        trading_ctx.trading_paused = False
        discrepancies = await startup_reconciliation(trading_ctx)
        assert trading_ctx.trading_paused is True
        # Reset for other tests
        trading_ctx.config.trading_mode = "paper"

    def test_stale_order_detection(self) -> None:
        """Old orders should be detected as stale."""
        from datetime import datetime, timedelta, timezone

        old_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        assert _is_stale_order({"created_at": old_time}, max_age_minutes=30) is True

        recent_time = datetime.now(timezone.utc).isoformat()
        assert _is_stale_order({"created_at": recent_time}, max_age_minutes=30) is False

    def test_stale_order_no_timestamp(self) -> None:
        assert _is_stale_order({}, max_age_minutes=30) is False
