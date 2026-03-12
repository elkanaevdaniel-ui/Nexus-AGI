"""Async wrappers around py-clob-client (synchronous SDK) and Gamma API."""

from __future__ import annotations

import asyncio
from typing import Any, Optional

import httpx
from loguru import logger

from src.config import StaticConfig
from src.data.schemas import GammaMarket, OrderBookSummary
from src.utils.rate_limiter import TokenBucketRateLimiter
from src.utils.retry import async_retry


class AsyncClobWrapper:
    """Async wrapper around the synchronous py-clob-client SDK.

    ALL calls are wrapped with asyncio.to_thread() to prevent blocking
    the event loop. The SDK uses `requests` internally.
    """

    def __init__(self, raw_client: Any) -> None:
        self._client = raw_client
        self._rate_limiter = TokenBucketRateLimiter(rate=5.0, burst=10)

    @property
    def raw(self) -> Any:
        """Access the underlying synchronous client (for signing, etc.)."""
        return self._client

    async def get_order_book(self, token_id: str) -> OrderBookSummary:
        """Get order book for a token, parsed into Pydantic model."""
        await self._rate_limiter.acquire()
        raw = await asyncio.to_thread(self._client.get_order_book, token_id)
        # py-clob-client returns an OrderBookSummary object with .dict() support
        if hasattr(raw, "__dict__"):
            data = raw.__dict__
        elif isinstance(raw, dict):
            data = raw
        else:
            data = {"bids": [], "asks": []}
        return OrderBookSummary.model_validate(data)

    async def get_midpoint(self, token_id: str) -> float:
        """Get midpoint price for a token."""
        await self._rate_limiter.acquire()
        result = await asyncio.to_thread(self._client.get_midpoint, token_id)
        if isinstance(result, (int, float)):
            return float(result)
        if isinstance(result, dict):
            return float(result.get("mid", 0.5))
        return float(result)

    async def get_price(self, token_id: str, side: str = "buy") -> float:
        """Get current price (more reliable than orderbook for live prices)."""
        await self._rate_limiter.acquire()
        result = await asyncio.to_thread(
            self._client.get_price, token_id, side
        )
        if not result:
            logger.warning(f"get_price returned empty for token {token_id}, defaulting to 0.0")
            return 0.0
        return float(result)

    async def create_order(self, order_args: Any) -> Any:
        """Create (sign) an order without posting it."""
        await self._rate_limiter.acquire()
        return await asyncio.to_thread(
            self._client.create_order, order_args
        )

    async def post_order(self, signed_order: Any, order_type: str = "GTC") -> dict:
        """Post a signed order to the CLOB."""
        await self._rate_limiter.acquire()
        result = await asyncio.to_thread(
            self._client.post_order, signed_order, order_type
        )
        return result if isinstance(result, dict) else {"result": str(result)}

    async def create_and_post_order(
        self, order_args: Any, order_type: Optional[str] = None
    ) -> dict:
        """Create, sign, and post an order in one call."""
        await self._rate_limiter.acquire()
        if order_type:
            result = await asyncio.to_thread(
                self._client.create_and_post_order, order_args, order_type
            )
        else:
            result = await asyncio.to_thread(
                self._client.create_and_post_order, order_args
            )
        return result if isinstance(result, dict) else {"result": str(result)}

    async def cancel(self, order_id: str) -> dict:
        """Cancel a specific order."""
        await self._rate_limiter.acquire()
        result = await asyncio.to_thread(self._client.cancel, order_id)
        return result if isinstance(result, dict) else {"result": str(result)}

    async def cancel_all(self) -> dict:
        """Cancel all open orders."""
        await self._rate_limiter.acquire()
        result = await asyncio.to_thread(self._client.cancel_all)
        return result if isinstance(result, dict) else {"result": str(result)}

    async def get_orders(self, params: Optional[Any] = None) -> list[dict]:
        """Get open orders, optionally filtered."""
        await self._rate_limiter.acquire()
        if params:
            result = await asyncio.to_thread(
                self._client.get_orders, params
            )
        else:
            result = await asyncio.to_thread(self._client.get_orders)
        return result if isinstance(result, list) else []

    async def get_balance_allowance(self, params: Any) -> dict:
        """Get balance and allowance for an asset type."""
        await self._rate_limiter.acquire()
        result = await asyncio.to_thread(
            self._client.get_balance_allowance, params
        )
        return result if isinstance(result, dict) else {}

    async def create_or_derive_api_creds(self) -> Any:
        """Create or derive API credentials (fixes 401 issues)."""
        await self._rate_limiter.acquire()
        return await asyncio.to_thread(
            self._client.create_or_derive_api_creds
        )


def build_clob_client(config: StaticConfig) -> Any:
    """Build a py-clob-client ClobClient from config.

    Returns None if private key is not set (paper trading without CLOB).
    """
    private_key = config.polymarket_private_key.get_secret_value()
    if not private_key:
        logger.warning("No private key configured — CLOB client unavailable")
        return None

    try:
        from py_clob_client.client import ClobClient

        client = ClobClient(
            host=config.polymarket_host,
            key=private_key,
            chain_id=config.polymarket_chain_id,
            signature_type=config.polymarket_signature_type,
        )
        if config.polymarket_proxy_address:
            client.set_proxy_address(config.polymarket_proxy_address)

        logger.info("CLOB client initialized successfully")
        return client
    except Exception as e:
        logger.error(f"Failed to initialize CLOB client: {e}")
        return None


class GammaClient:
    """Async client for the Gamma Markets API (public endpoints)."""

    def __init__(self, base_url: str = "https://gamma-api.polymarket.com") -> None:
        self._base_url = base_url
        self._http = httpx.AsyncClient(
            base_url=base_url,
            timeout=30.0,
            headers={"Accept": "application/json"},
        )
        self._rate_limiter = TokenBucketRateLimiter(rate=5.0, burst=10)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._http.aclose()

    @async_retry(max_retries=3, retryable_exceptions=(httpx.HTTPError,))
    async def get_markets(
        self,
        limit: int = 100,
        offset: int = 0,
        active: bool = True,
        closed: bool = False,
        order: str = "volume",
        ascending: bool = False,
    ) -> list[GammaMarket]:
        """Fetch markets from Gamma API with filtering."""
        await self._rate_limiter.acquire()
        params = {
            "limit": limit,
            "offset": offset,
            "active": str(active).lower(),
            "closed": str(closed).lower(),
            "order": order,
            "ascending": str(ascending).lower(),
        }
        response = await self._http.get("/markets", params=params)
        response.raise_for_status()
        data = response.json()

        markets: list[GammaMarket] = []
        for item in data:
            try:
                markets.append(GammaMarket.model_validate(item))
            except Exception as e:
                logger.warning(
                    f"Skipping malformed market data: {e}"
                )
        return markets

    @async_retry(max_retries=3, retryable_exceptions=(httpx.HTTPError,))
    async def get_market(self, market_id: str) -> Optional[GammaMarket]:
        """Fetch a single market by ID."""
        await self._rate_limiter.acquire()
        response = await self._http.get(f"/markets/{market_id}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data = response.json()
        return GammaMarket.model_validate(data)

    @async_retry(max_retries=3, retryable_exceptions=(httpx.HTTPError,))
    async def get_events(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """Fetch events (groups of related markets)."""
        await self._rate_limiter.acquire()
        params = {"limit": limit, "offset": offset}
        response = await self._http.get("/events", params=params)
        response.raise_for_status()
        return response.json()
