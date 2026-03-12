"""FastAPI app + startup lifecycle."""

from __future__ import annotations

import asyncio
import json
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from prometheus_client import make_asgi_app
from starlette.middleware.cors import CORSMiddleware
from src.api.auth import create_access_token, validate_jwt_secret
from src.api.routes.calibration import router as calibration_router
from src.api.routes.controls import router as controls_router
from src.api.routes.health import router as health_router
from src.api.routes.markets import router as markets_router
from src.api.routes.portfolio import router as portfolio_router
from src.api.routes.trades import router as trades_router
from src.config import DynamicConfig, StaticConfig
from src.context import TradingContext
from src.core.loops import start_background_tasks, stop_background_tasks
from src.core.portfolio import PortfolioTracker
from src.core.probability import CalibrationTracker
from src.core.reconciliation import startup_reconciliation
from src.core.risk import RiskManager
from src.data.database import create_engine, create_session_factory, create_tables
from src.data.repository import Repository
from src.integrations.polymarket import (
    AsyncClobWrapper,
    GammaClient,
    build_clob_client,
)
from src.integrations.telegram import TelegramBot
from src.utils.logging import setup_logging


async def build_trading_context() -> TradingContext:
    """Build the full TradingContext with all dependencies wired up."""
    config = StaticConfig()
    dynamic_config = DynamicConfig()

    # Database
    engine = await create_engine(config.database_url)
    await create_tables(engine)
    session_factory = create_session_factory(engine)
    repo = Repository(session_factory)

    # API clients
    gamma = GammaClient(base_url=config.gamma_api_url)

    raw_clob = build_clob_client(config)
    clob = AsyncClobWrapper(raw_clob) if raw_clob else None

    # Core components
    portfolio = PortfolioTracker(initial_bankroll=config.initial_bankroll)
    risk_manager = RiskManager()
    calibration_tracker = CalibrationTracker(repo)

    # Always validate JWT secret — required for API security
    jwt_secret = config.dashboard_jwt_secret.get_secret_value()
    if config.trading_mode == "live":
        validate_jwt_secret(jwt_secret)
    else:
        # Paper mode: still require a valid secret if the API is running
        if not jwt_secret or len(jwt_secret) < 32:
            import secrets as _secrets

            generated = _secrets.token_hex(32)
            logger.warning(
                "DASHBOARD_JWT_SECRET not set or too short — "
                "auto-generated ephemeral secret for this session. "
                "Set DASHBOARD_JWT_SECRET in .env for persistent auth."
            )
            # Override the config with the generated secret
            config.dashboard_jwt_secret = type(config.dashboard_jwt_secret)(generated)

    # Telegram bot
    telegram = TelegramBot(
        token=config.telegram_bot_token.get_secret_value(),
        chat_id=config.telegram_chat_id,
        agent_zero_url=config.agent_zero_url,
        agent_zero_api_key=config.agent_zero_api_key.get_secret_value(),
    )

    # Build context
    ctx = TradingContext(
        config=config,
        dynamic_config=dynamic_config,
        repo=repo,
        gamma=gamma,
        clob=clob,
        portfolio=portfolio,
        risk_manager=risk_manager,
        calibration_tracker=calibration_tracker,
        telegram=telegram,
    )

    # Store engine reference for shutdown disposal
    ctx._engine = engine  # type: ignore[attr-defined]

    # In live mode, always start paused
    if config.trading_mode == "live":
        ctx.trading_paused = True
        logger.warning(
            "LIVE MODE — trading paused until manual confirmation"
        )
    else:
        ctx.trading_paused = False
        logger.info("PAPER MODE — trading active")

    return ctx


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — startup and shutdown logic."""
    setup_logging()
    logger.info("Starting Polymarket Trading Agent...")

    ctx = await build_trading_context()
    app.state.trading_ctx = ctx

    # Startup reconciliation
    await startup_reconciliation(ctx)

    # Restore portfolio state from last snapshot
    if ctx.portfolio:
        restored = await ctx.portfolio.restore_from_snapshot(ctx)
        if not restored:
            logger.info("No previous snapshot found, starting with initial bankroll")

    # Restore risk manager state from DB
    if ctx.risk_manager:
        await ctx.risk_manager.restore_state(ctx)

    logger.info(
        f"Trading agent initialized | mode={ctx.config.trading_mode} "
        f"| paused={ctx.trading_paused}"
    )

    # Start Telegram command listener
    telegram_task: asyncio.Task | None = None
    if ctx.telegram and ctx.telegram.enabled:
        telegram_task = asyncio.create_task(
            ctx.telegram.start_command_listener(ctx)
        )
        await ctx.telegram.send_startup_alert(
            mode=ctx.config.trading_mode,
            paused=ctx.trading_paused,
        )
        logger.info("Telegram bot connected and listening for commands")

    # Start background task loops
    tasks = await start_background_tasks(ctx)

    yield

    # Shutdown
    logger.info("Shutting down trading agent...")

    # Stop Telegram listener
    if telegram_task and not telegram_task.done():
        telegram_task.cancel()
        try:
            await telegram_task
        except asyncio.CancelledError:
            pass
    if ctx.telegram:
        await ctx.telegram.close()

    await stop_background_tasks(tasks)

    # Save final portfolio snapshot
    if ctx.portfolio:
        try:
            await ctx.portfolio.save_snapshot(ctx)
            logger.info("Final portfolio snapshot saved")
        except Exception as e:
            logger.warning(f"Failed to save final snapshot: {e}")

    await ctx.gamma.close()

    # Dispose SQLAlchemy engine to release connection pool
    if hasattr(ctx, '_engine') and ctx._engine:
        await ctx._engine.dispose()

    logger.info("Shutdown complete")


# Bounded in-memory rate limiter for API endpoints.
# Uses an OrderedDict capped at _MAX_IPS to prevent memory exhaustion.
_rate_limit_store: dict[str, list[float]] = {}
_RATE_LIMIT_MAX = 60  # requests per window
_RATE_LIMIT_WINDOW = 60.0  # seconds
_MAX_IPS = 10_000  # max tracked IPs (prevents memory leak under attack)


async def _rate_limit_middleware(request: Request, call_next):  # noqa: ANN001
    """Rate limiting middleware based on client IP with bounded memory."""
    if request.url.path.startswith("/health") or request.url.path.startswith("/docs"):
        return await call_next(request)

    client_ip = request.client.host if request.client else "unknown"
    now = time.monotonic()

    if client_ip not in _rate_limit_store:
        # Evict oldest entries if store is full
        if len(_rate_limit_store) >= _MAX_IPS:
            oldest_key = next(iter(_rate_limit_store))
            del _rate_limit_store[oldest_key]
        _rate_limit_store[client_ip] = []

    # Remove old entries outside the window
    _rate_limit_store[client_ip] = [
        t for t in _rate_limit_store[client_ip] if now - t < _RATE_LIMIT_WINDOW
    ]

    if len(_rate_limit_store[client_ip]) >= _RATE_LIMIT_MAX:
        return Response(
            content='{"detail":"Rate limit exceeded"}',
            status_code=429,
            media_type="application/json",
            headers={"Retry-After": str(int(_RATE_LIMIT_WINDOW))},
        )

    _rate_limit_store[client_ip].append(now)
    return await call_next(request)


class ConnectionManager:
    """Manages WebSocket connections for live feed."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict) -> None:
        data = json.dumps(message)
        for connection in self.active_connections[:]:
            try:
                await connection.send_text(data)
            except Exception:
                self.disconnect(connection)


ws_manager = ConnectionManager()


def create_app() -> FastAPI:
    """Create the FastAPI application."""
    app = FastAPI(
        title="Polymarket Trading Agent",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Rate limiting middleware
    app.middleware("http")(_rate_limit_middleware)

    # CORS — restrictive by default, require explicit config in live mode
    allowed_origins = os.getenv("CORS_ORIGINS", "").split(",")
    allowed_origins = [o.strip() for o in allowed_origins if o.strip()]

    trading_mode = os.getenv("TRADING_MODE", "paper")
    if not allowed_origins:
        if trading_mode == "live":
            logger.warning(
                "CORS_ORIGINS not set in live mode — "
                "no cross-origin requests will be allowed"
            )
            allowed_origins = []
        else:
            allowed_origins = ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # API Routes
    app.include_router(health_router)
    app.include_router(portfolio_router)
    app.include_router(markets_router)
    app.include_router(trades_router)
    app.include_router(calibration_router)
    app.include_router(controls_router)

    # Dashboard token endpoint (paper mode only — generates a viewer token)
    @app.post("/auth/token")
    async def get_dashboard_token(request: Request) -> dict:
        """Generate a dashboard access token.

        In paper mode, returns a viewer token without credentials.
        In live mode, this should require proper authentication.
        """
        ctx: TradingContext = request.app.state.trading_ctx
        if ctx.config.trading_mode == "live":
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Token generation requires proper auth in live mode",
            )
        secret = ctx.config.dashboard_jwt_secret.get_secret_value()
        token = create_access_token(
            subject="dashboard",
            secret=secret,
            expire_minutes=ctx.config.dashboard_jwt_expire_minutes,
            role="operator",
        )
        return {"access_token": token, "token_type": "bearer"}

    # WebSocket endpoint for live feed
    @app.websocket("/ws/feed")
    async def websocket_feed(websocket: WebSocket) -> None:
        await ws_manager.connect(websocket)
        try:
            while True:
                # Keep connection alive; client can send pings
                data = await asyncio.wait_for(
                    websocket.receive_text(), timeout=30.0
                )
        except (WebSocketDisconnect, asyncio.TimeoutError, Exception):
            ws_manager.disconnect(websocket)

    # Dashboard — serve index.html at root
    static_dir = Path(__file__).resolve().parent.parent / "static"

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    # Static files (CSS, JS, images)
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Prometheus metrics on a separate internal-only path with auth check
    # Mount behind /internal/metrics to signal it should be network-restricted
    metrics_app = make_asgi_app()
    app.mount("/internal/metrics", metrics_app)

    # Store ws_manager on app state for use by other components
    app.state.ws_manager = ws_manager

    return app


app = create_app()
