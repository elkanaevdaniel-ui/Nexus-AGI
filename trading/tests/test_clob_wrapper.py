"""Tests for AsyncClobWrapper — ensures all SDK calls run via asyncio.to_thread."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.integrations.polymarket import AsyncClobWrapper


class TestAsyncClobWrapper:
    """Tests for the async CLOB wrapper."""

    @pytest.mark.asyncio
    async def test_get_order_book(self, mock_clob: AsyncClobWrapper) -> None:
        """Should return parsed OrderBookSummary."""
        ob = await mock_clob.get_order_book("token_123")
        assert ob.asset_id == "test_token"
        assert len(ob.bids) == 1
        assert len(ob.asks) == 1
        assert ob.bids[0].price == "0.45"

    @pytest.mark.asyncio
    async def test_get_midpoint(self, mock_clob: AsyncClobWrapper) -> None:
        """Should return float midpoint."""
        mid = await mock_clob.get_midpoint("token_123")
        assert mid == 0.50

    @pytest.mark.asyncio
    async def test_get_price(self, mock_clob: AsyncClobWrapper) -> None:
        """Should return float price."""
        price = await mock_clob.get_price("token_123", "buy")
        assert price == 0.50

    @pytest.mark.asyncio
    async def test_post_order(self, mock_clob: AsyncClobWrapper) -> None:
        """Should post a signed order."""
        result = await mock_clob.post_order({"signed": True}, "GTC")
        assert "orderID" in result

    @pytest.mark.asyncio
    async def test_cancel_all(self, mock_clob: AsyncClobWrapper) -> None:
        """Should cancel all orders."""
        result = await mock_clob.cancel_all()
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_get_orders(self, mock_clob: AsyncClobWrapper) -> None:
        """Should return list of orders."""
        orders = await mock_clob.get_orders()
        assert isinstance(orders, list)

    @pytest.mark.asyncio
    async def test_raw_client_accessible(
        self, mock_clob: AsyncClobWrapper
    ) -> None:
        """Raw client should be accessible for signing operations."""
        assert mock_clob.raw is not None

    @pytest.mark.asyncio
    async def test_calls_run_in_thread(self) -> None:
        """Verify SDK calls are dispatched to thread pool."""
        import asyncio
        from unittest.mock import patch

        mock_raw = MagicMock()
        mock_raw.get_midpoint.return_value = 0.42
        wrapper = AsyncClobWrapper(mock_raw)

        with patch.object(
            asyncio, "to_thread", wraps=asyncio.to_thread
        ) as mock_to_thread:
            result = await wrapper.get_midpoint("token_abc")
            mock_to_thread.assert_called_once()
            assert result == 0.42
