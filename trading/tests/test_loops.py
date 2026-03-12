"""Tests for background task loop management."""

from __future__ import annotations

import asyncio

import pytest

from src.core.loops import start_background_tasks, stop_background_tasks


class TestBackgroundTasks:
    """Test task lifecycle management."""

    @pytest.mark.asyncio
    async def test_start_and_stop_tasks(self, trading_ctx) -> None:
        """Background tasks should start and stop cleanly."""
        tasks = await start_background_tasks(trading_ctx)
        assert len(tasks) == 5

        # All tasks should be running
        for task in tasks:
            assert not task.done()

        # Stop them
        await stop_background_tasks(tasks)

        # All tasks should be done
        for task in tasks:
            assert task.done()

    @pytest.mark.asyncio
    async def test_task_names(self, trading_ctx) -> None:
        """Each task should have a descriptive name."""
        tasks = await start_background_tasks(trading_ctx)
        names = {t.get_name() for t in tasks}
        assert "scan_loop" in names
        assert "reconciliation_loop" in names
        assert "resolution_loop" in names
        assert "arbitrage_loop" in names
        assert "price_update_loop" in names
        await stop_background_tasks(tasks)

    @pytest.mark.asyncio
    async def test_paused_scan_loop_skips(self, trading_ctx) -> None:
        """Scan loop should skip when trading is paused."""
        trading_ctx.trading_paused = True

        # Run one iteration of the scan loop by mocking sleep to raise
        from unittest.mock import AsyncMock, patch

        call_count = 0

        async def mock_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                raise asyncio.CancelledError()

        with patch("src.core.loops.asyncio.sleep", side_effect=mock_sleep):
            from src.core.loops import scan_loop

            with pytest.raises(asyncio.CancelledError):
                await scan_loop(trading_ctx)

        trading_ctx.trading_paused = False
