"""Shared fixtures for tests — mock CLOB, mock LLMs, in-memory DB."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, AsyncGenerator, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config import DynamicConfig, StaticConfig
from src.context import TradingContext
from src.data.database import create_engine, create_session_factory, create_tables
from src.data.repository import Repository
from src.integrations.polymarket import AsyncClobWrapper, GammaClient


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def static_config() -> StaticConfig:
    """Static config with test defaults."""
    return StaticConfig(
        polymarket_private_key="test_key_not_real",
        anthropic_api_key="test_anthropic_key",
        openai_api_key="test_openai_key",
        google_api_key="test_google_key",
        openrouter_api_key="test_openrouter_key",
        dashboard_jwt_secret="test_jwt_secret_for_testing_only",
        database_url="sqlite+aiosqlite:///:memory:",
        trading_mode="paper",
        initial_bankroll=1000.0,
    )


@pytest.fixture
def dynamic_config() -> DynamicConfig:
    """Dynamic config with test defaults."""
    return DynamicConfig()


@pytest_asyncio.fixture
async def db_engine():
    """In-memory SQLite engine for testing."""
    engine = await create_engine("sqlite+aiosqlite:///:memory:")
    await create_tables(engine)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(db_engine) -> async_sessionmaker[AsyncSession]:
    """Session factory for test DB."""
    return create_session_factory(db_engine)


@pytest_asyncio.fixture
async def repo(session_factory) -> Repository:
    """Repository connected to in-memory test DB."""
    return Repository(session_factory)


@pytest.fixture
def mock_clob_raw() -> MagicMock:
    """Mock raw py-clob-client ClobClient."""
    client = MagicMock()
    client.get_order_book.return_value = {
        "market": "test_market",
        "asset_id": "test_token",
        "bids": [{"price": "0.45", "size": "100"}],
        "asks": [{"price": "0.55", "size": "100"}],
        "hash": "",
        "timestamp": "",
    }
    client.get_midpoint.return_value = 0.50
    client.get_price.return_value = 0.50
    client.create_order.return_value = {"signed": True}
    client.post_order.return_value = {"orderID": "test_order_123"}
    client.cancel.return_value = {"cancelled": True}
    client.cancel_all.return_value = {"cancelled": []}
    client.get_orders.return_value = []
    client.get_balance_allowance.return_value = {"balance": "1000"}
    return client


@pytest.fixture
def mock_clob(mock_clob_raw) -> AsyncClobWrapper:
    """AsyncClobWrapper with mocked underlying client."""
    return AsyncClobWrapper(mock_clob_raw)


@pytest.fixture
def mock_gamma() -> GammaClient:
    """Mock GammaClient — never hits real API."""
    client = GammaClient.__new__(GammaClient)
    client._base_url = "https://gamma-api.polymarket.com"
    client._http = AsyncMock()
    client._rate_limiter = MagicMock()
    client._rate_limiter.acquire = AsyncMock()
    return client


@pytest_asyncio.fixture
async def trading_ctx(
    static_config, dynamic_config, repo, mock_clob, mock_gamma
) -> TradingContext:
    """Fully wired TradingContext for testing."""
    from src.core.portfolio import PortfolioTracker
    from src.core.probability import CalibrationTracker
    from src.core.risk import RiskManager

    return TradingContext(
        config=static_config,
        dynamic_config=dynamic_config,
        repo=repo,
        gamma=mock_gamma,
        clob=mock_clob,
        portfolio=PortfolioTracker(initial_bankroll=1000.0),
        risk_manager=RiskManager(),
        calibration_tracker=CalibrationTracker(repo),
        trading_paused=False,
    )
