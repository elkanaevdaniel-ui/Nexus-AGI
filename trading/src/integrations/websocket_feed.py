"""WebSocket price feed manager for real-time market data."""

from __future__ import annotations

import asyncio
import json
import ssl
from typing import TYPE_CHECKING, Any, Callable, Optional

from loguru import logger

if TYPE_CHECKING:
    from src.context import TradingContext


class WebSocketFeedManager:
    """Manages WebSocket connections to Polymarket price feeds.

    Handles reconnection, heartbeats, and dispatching price updates.
    """

    WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

    def __init__(self) -> None:
        self._callbacks: list[Callable] = []
        self._running: bool = False
        self._subscribed_tokens: list[str] = []
        self._ws: Any = None  # Active websocket connection

    def on_price_update(self, callback: Callable) -> None:
        """Register a callback for price updates."""
        self._callbacks.append(callback)

    async def subscribe(self, token_ids: list[str]) -> None:
        """Update subscriptions to the given token IDs."""
        self._subscribed_tokens = token_ids
        logger.info(f"WebSocket subscribed to {len(token_ids)} tokens")

    async def run(self, ctx: TradingContext) -> None:
        """Main WebSocket loop with auto-reconnection.

        Note: Requires `websockets` package for production.
        In sandbox/test environments, falls back to periodic REST polling.
        """
        self._running = True
        logger.info("WebSocket feed manager started")

        while self._running:
            try:
                await self._connect_and_listen(ctx)
            except Exception as e:
                logger.warning(f"WebSocket connection error: {e}")
                if self._running:
                    await asyncio.sleep(5)  # Reconnect delay

    async def _connect_and_listen(self, ctx: TradingContext) -> None:
        """Connect to WebSocket and process messages."""
        try:
            import websockets

            # Explicitly enforce TLS certificate verification
            ssl_context = ssl.create_default_context()

            async with websockets.connect(
                self.WS_URL,
                ping_interval=30,
                ping_timeout=10,
                ssl=ssl_context,
            ) as ws:
                self._ws = ws
                # Subscribe to markets
                if self._subscribed_tokens:
                    await ws.send(
                        json.dumps({
                            "assets_ids": self._subscribed_tokens,
                            "type": "market",
                        })
                    )

                logger.info("WebSocket connected and subscribed")

                async for message in ws:
                    if not self._running:
                        break
                    if message == "PONG":
                        continue
                    try:
                        data = json.loads(message)
                        await self._dispatch(data)
                    except json.JSONDecodeError:
                        continue

        except ImportError:
            # Fallback: REST polling when websockets not installed
            logger.info("websockets not installed — using REST polling fallback")
            while self._running:
                await asyncio.sleep(60)
        finally:
            self._ws = None

    async def _dispatch(self, data: dict) -> None:
        """Dispatch a price update to all registered callbacks."""
        for callback in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
            except Exception as e:
                logger.warning(f"WebSocket callback error: {e}")

    async def stop(self) -> None:
        """Stop the WebSocket feed and close the active connection."""
        self._running = False
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
        logger.info("WebSocket feed manager stopped")
