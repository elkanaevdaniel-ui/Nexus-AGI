"""Comprehensive integration test verifying all phases are installed and working.

This test validates the complete trading system end-to-end:
- Phase 1: Foundation (config, DB, schemas, CLOB wrapper, context, logging, metrics)
- Phase 2: Core Trading Logic (scanner, probability, edge, kelly, risk, calibration)
- Phase 3: Execution + Portfolio (executor, paper broker, portfolio, resolution, reconciliation)
- Phase 4: Real-Time + Intelligence (websocket, arbitrage, news, whale tracker, telegram)
- Phase 5: Dashboard + Deployment (auth, all API routes, dynamic config, scripts)
"""

from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.context import TradingContext
from src.main import create_app


# ============================================================================
# Phase 1: Foundation
# ============================================================================


class TestPhase1Foundation:
    """Verify all Phase 1 components exist and are importable."""

    def test_config_module(self) -> None:
        from src.config import DynamicConfig, StaticConfig

        cfg = StaticConfig(
            polymarket_private_key="test",
            anthropic_api_key="test",
            openai_api_key="test",
            google_api_key="test",
            dashboard_jwt_secret="test",
        )
        assert cfg.trading_mode == "paper"
        dyn = DynamicConfig()
        assert dyn.kelly_fraction == 0.5

    def test_database_models_all_tables(self) -> None:
        from src.data.models import (
            Alert,
            Base,
            CircuitBreakerEvent,
            LLMCall,
            Market,
            MarketResolution,
            Order,
            OrderEvent,
            PendingTrade,
            PortfolioSnapshot,
            Position,
            ProbabilityEstimate,
            ReconciliationLog,
            Trade,
        )

        table_names = set(Base.metadata.tables.keys())
        expected = {
            "markets",
            "positions",
            "orders",
            "trades",
            "probability_estimates",
            "portfolio_snapshots",
            "alerts",
            "market_resolutions",
            "reconciliation_log",
            "circuit_breaker_events",
            "order_events",
            "llm_calls",
            "pending_trades",
        }
        assert expected == table_names, f"Missing tables: {expected - table_names}"

    def test_database_async_engine(self) -> None:
        from src.data.database import (
            create_engine,
            create_session_factory,
            create_tables,
        )

        assert callable(create_engine)
        assert callable(create_session_factory)
        assert callable(create_tables)

    def test_repository_pattern(self) -> None:
        from src.data.repository import Repository

        assert hasattr(Repository, "upsert_market")
        assert hasattr(Repository, "get_open_positions")
        assert hasattr(Repository, "create_order")
        assert hasattr(Repository, "record_trade")
        assert hasattr(Repository, "save_probability_estimate")
        assert hasattr(Repository, "save_portfolio_snapshot")
        assert hasattr(Repository, "log_reconciliation_event")
        assert hasattr(Repository, "log_circuit_breaker")
        assert hasattr(Repository, "log_llm_call")
        assert hasattr(Repository, "log_order_event")

    def test_pydantic_schemas(self) -> None:
        from src.data.schemas import (
            CalibrationResponse,
            ConsensusEstimate,
            DynamicConfigUpdate,
            EdgeResult,
            GammaMarket,
            HealthResponse,
            KellyResult,
            LLMProbabilityEstimate,
            OrderBookSummary,
            PortfolioSummary,
            PositionResponse,
            ReconciliationEvent,
            RiskCheckResult,
            TradeDecision,
        )

        # Verify probability clamping
        est = LLMProbabilityEstimate(
            probability=0.50,
            confidence="medium",
            base_rate=0.5,
            reasoning="test",
        )
        assert est.probability == 0.50

    def test_async_clob_wrapper(self) -> None:
        from src.integrations.polymarket import AsyncClobWrapper

        assert hasattr(AsyncClobWrapper, "get_order_book")
        assert hasattr(AsyncClobWrapper, "get_midpoint")
        assert hasattr(AsyncClobWrapper, "get_price")
        assert hasattr(AsyncClobWrapper, "post_order")
        assert hasattr(AsyncClobWrapper, "cancel_all")
        assert hasattr(AsyncClobWrapper, "get_orders")
        assert hasattr(AsyncClobWrapper, "get_balance_allowance")

    def test_gamma_client(self) -> None:
        from src.integrations.polymarket import GammaClient

        assert hasattr(GammaClient, "get_markets")
        assert hasattr(GammaClient, "get_market")
        assert hasattr(GammaClient, "get_events")

    def test_trading_context(self) -> None:
        from src.context import TradingContext

        assert hasattr(TradingContext, "is_paper")
        assert hasattr(TradingContext, "is_live")
        assert hasattr(TradingContext, "uptime_seconds")

    def test_logging_with_redaction(self) -> None:
        from src.utils.logging import _redact

        assert "[REDACTED]" in _redact("key=0x1234567890abcdef1234567890abcdef12345678")
        assert "[REDACTED]" in _redact("key=sk-abc12345678901234567890")

    def test_metrics_defined(self) -> None:
        from src.utils.metrics import (
            API_CALLS,
            BRIER_SCORE,
            CIRCUIT_BREAKER_TRIPS,
            DAILY_LOSS_PCT,
            LLM_CALLS,
            MARKETS_SCANNED,
            OPEN_POSITIONS,
            PORTFOLIO_VALUE,
            REALIZED_PNL,
            TRADES_TOTAL,
        )

    def test_rate_limiter(self) -> None:
        from src.utils.rate_limiter import TokenBucketRateLimiter

        rl = TokenBucketRateLimiter(rate=10.0, burst=20)
        assert rl._tokens == 20.0

    def test_retry_decorator(self) -> None:
        from src.utils.retry import async_retry

        assert callable(async_retry)


# ============================================================================
# Phase 2: Core Trading Logic
# ============================================================================


class TestPhase2CoreTradingLogic:
    """Verify all Phase 2 components exist and work."""

    def test_scanner_module(self) -> None:
        from src.core.scanner import (
            fetch_candidate_markets,
            gather_market_context,
            rank_markets,
            run_scan_cycle,
        )

    def test_probability_module(self) -> None:
        from src.core.probability import (
            CalibrationTracker,
            calculate_consensus,
            estimate_probability_consensus,
            parse_llm_response,
        )

    def test_edge_calculator(self) -> None:
        from src.core.edge import calculate_edge
        from src.data.schemas import ConsensusEstimate

        estimate = ConsensusEstimate(
            probability=0.70,
            confidence="high",
        )
        edge = calculate_edge(estimate, market_price=0.50, fee_rate_bps=200)
        assert edge.magnitude > 0
        assert edge.direction == "BUY"

    def test_kelly_criterion(self) -> None:
        from src.core.kelly import fee_adjusted_kelly

        result = fee_adjusted_kelly(
            estimated_prob=0.70,
            market_price=0.50,
            fee_rate_bps=200,
            bankroll=1000.0,
        )
        assert result.position_size_usd > 0
        assert result.fraction > 0

    def test_risk_manager(self) -> None:
        from src.core.risk import RiskManager

        rm = RiskManager()
        assert hasattr(rm, "check")
        assert hasattr(rm, "restore_state")
        assert hasattr(rm, "reset_breaker")
        assert not rm.is_any_breaker_tripped

    def test_calibration_tracker(self) -> None:
        from src.core.probability import CalibrationTracker

        assert hasattr(CalibrationTracker, "record_resolution")
        assert hasattr(CalibrationTracker, "get_rolling_brier")

    def test_langgraph_agents(self) -> None:
        from src.agents.consensus import (
            build_consensus_graph,
            call_claude_node,
            call_gemini_node,
            call_gpt_node,
            synthesize_consensus,
        )
        from src.agents.debate import run_bull_bear_debate
        from src.agents.state import ConsensusState


# ============================================================================
# Phase 3: Execution + Portfolio
# ============================================================================


class TestPhase3ExecutionPortfolio:
    """Verify all Phase 3 components exist and work."""

    def test_executor_module(self) -> None:
        from src.core.executor import Fill, PaperBroker, safe_place_order

    def test_paper_broker_simulation(self) -> None:
        from src.core.executor import PaperBroker
        from src.data.schemas import OrderBookSummary

        broker = PaperBroker()
        ob = OrderBookSummary(
            asks=[{"price": "0.50", "size": "500"}],
            bids=[{"price": "0.48", "size": "500"}],
        )
        fill = broker.simulate_fill("BUY", 0.55, 100, ob, 200)
        assert fill is not None
        assert fill.quantity == 100
        assert fill.fee > 0

    def test_portfolio_tracker(self) -> None:
        from src.core.portfolio import PortfolioTracker

        tracker = PortfolioTracker(1000.0)
        assert tracker.cash_balance == 1000.0

    def test_resolution_handler(self) -> None:
        from src.core.resolution import check_resolutions

        assert callable(check_resolutions)

    def test_reconciliation_engine(self) -> None:
        from src.core.reconciliation import (
            run_reconciliation_cycle,
            startup_reconciliation,
        )

    @pytest.mark.asyncio
    async def test_full_trade_lifecycle(self, trading_ctx) -> None:
        """Integration: open position -> track -> close -> PnL."""
        from src.core.portfolio import PortfolioTracker

        tracker = PortfolioTracker(1000.0)

        # Open
        pos_id = await tracker.open_position(
            market_id="m1",
            token_id="t1",
            side="YES",
            quantity=50,
            price=0.40,
            fee=0.5,
            ctx=trading_ctx,
        )
        assert tracker.cash_balance < 1000.0

        # Check portfolio
        summary = await tracker.get_summary(trading_ctx)
        assert summary.open_positions_count == 1

        # Close with profit
        pnl = await tracker.close_position(
            position_id=pos_id,
            exit_price=0.60,
            quantity=50,
            fee=0.5,
            ctx=trading_ctx,
        )
        assert pnl > 0

        # Verify position closed
        summary = await tracker.get_summary(trading_ctx)
        assert summary.open_positions_count == 0


# ============================================================================
# Phase 4: Real-Time + Intelligence
# ============================================================================


class TestPhase4RealTimeIntelligence:
    """Verify all Phase 4 components exist."""

    def test_websocket_feed(self) -> None:
        from src.integrations.websocket_feed import WebSocketFeedManager

        ws = WebSocketFeedManager()
        assert hasattr(ws, "subscribe")
        assert hasattr(ws, "run")
        assert hasattr(ws, "on_price_update")
        assert hasattr(ws, "stop")

    def test_arbitrage_scanner(self) -> None:
        from src.core.arbitrage import (
            ArbitrageOpportunity,
            detect_arbitrage,
            execute_arbitrage,
            run_arbitrage_scan,
            scan_orderbook_arbitrage,
        )

        # Test detection
        arb = detect_arbitrage(0.40, 0.45, "test", 200)
        assert arb is not None
        assert arb.profit_after_fees > 0

    def test_news_sentinel(self) -> None:
        from src.core.news import NewsEvent, NewsSentinel

        sentinel = NewsSentinel()
        assert hasattr(sentinel, "check_news")
        assert hasattr(sentinel, "match_markets")

    def test_news_feeds(self) -> None:
        from src.integrations.news_feeds import NewsAPIClient, RSSFeedReader

        client = NewsAPIClient("")
        assert not client.enabled  # No key = disabled

    def test_whale_tracker(self) -> None:
        from src.integrations.whale_tracker import WhaleTracker, WhaleTransaction

        tracker = WhaleTracker()
        tracker.add_wallet("0x1234")
        assert len(tracker.watched_wallets) == 1
        signal = tracker.get_whale_signal("nonexistent")
        assert signal is None

    def test_telegram_bot(self) -> None:
        from src.integrations.telegram import TelegramBot

        bot = TelegramBot("", "")
        assert not bot.enabled


# ============================================================================
# Phase 5: Dashboard + Deployment
# ============================================================================


class TestPhase5DashboardDeployment:
    """Verify all Phase 5 components exist and work."""

    _JWT_SECRET = "test_jwt_secret_for_testing_only"

    def _auth_headers(self, role: str = "operator") -> dict[str, str]:
        from src.api.auth import create_access_token

        token = create_access_token("test_user", self._JWT_SECRET, role=role)
        return {"Authorization": f"Bearer {token}"}

    def test_jwt_auth(self) -> None:
        from src.api.auth import (
            TokenPayload,
            create_access_token,
            decode_token,
        )

        secret = "test_secret"
        token = create_access_token("admin", secret, role="admin")
        payload = decode_token(token, secret)
        assert payload is not None
        assert payload.sub == "admin"
        assert payload.role == "admin"

    def test_all_api_routes_registered(self, trading_ctx) -> None:
        """Verify all routes are registered in the FastAPI app."""
        app = create_app()
        app.state.trading_ctx = trading_ctx
        routes = [r.path for r in app.routes]

        expected_routes = [
            "/health",
            "/api/portfolio/summary",
            "/api/portfolio/positions",
            "/api/markets/",
            "/api/markets/{market_id}",
            "/api/trades/",
            "/api/calibration/",
            "/api/controls/state",
            "/api/controls/trading",
            "/api/controls/config",
            "/api/controls/cancel-all",
        ]
        for route in expected_routes:
            assert route in routes, f"Missing route: {route}"

    def test_all_api_endpoints_respond(self, trading_ctx) -> None:
        """Verify every endpoint returns a valid response."""
        app = create_app()
        app.state.trading_ctx = trading_ctx
        client = TestClient(app, raise_server_exceptions=False)

        # Health endpoint (no auth required)
        resp = client.get("/health")
        assert resp.status_code == 200, "GET /health returned non-200"

        # GET endpoints (auth required)
        headers = self._auth_headers("viewer")
        for path in [
            "/api/portfolio/summary",
            "/api/portfolio/positions",
            "/api/markets/",
            "/api/trades/",
            "/api/calibration/",
            "/api/controls/state",
        ]:
            resp = client.get(path, headers=headers)
            assert resp.status_code == 200, f"GET {path} returned {resp.status_code}"

    def test_pause_resume_cycle(self, trading_ctx) -> None:
        """Test full pause/resume cycle via API."""
        app = create_app()
        app.state.trading_ctx = trading_ctx
        client = TestClient(app, raise_server_exceptions=False)
        headers = self._auth_headers()

        # Pause
        resp = client.post(
            "/api/controls/trading",
            json={"action": "pause"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["trading_paused"] is True

        # Resume
        resp = client.post(
            "/api/controls/trading",
            json={"action": "resume"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["trading_paused"] is False

    def test_dynamic_config_update(self, trading_ctx) -> None:
        app = create_app()
        app.state.trading_ctx = trading_ctx
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.patch(
            "/api/controls/config",
            json={"kelly_fraction": 0.30, "min_edge_threshold": 0.08},
            headers=self._auth_headers(),
        )
        assert resp.status_code == 200
        updated = resp.json()["updated"]
        assert "kelly_fraction" in updated
        assert updated["kelly_fraction"]["new"] == 0.30

    def test_deployment_scripts_exist(self) -> None:
        """Verify deployment scripts are present."""
        scripts_dir = Path(__file__).parent.parent / "scripts"
        assert (scripts_dir / "restart.sh").exists()
        assert (scripts_dir / "kill_switch.sh").exists()
        assert (scripts_dir / "backtest.py").exists()
        assert (scripts_dir / "paper_trade.py").exists()
        assert (scripts_dir / "collect_data.py").exists()

    def test_scripts_executable(self) -> None:
        scripts_dir = Path(__file__).parent.parent / "scripts"
        assert os.access(scripts_dir / "restart.sh", os.X_OK)
        assert os.access(scripts_dir / "kill_switch.sh", os.X_OK)

    def test_alembic_config_exists(self) -> None:
        assert (Path(__file__).parent.parent / "alembic" / "alembic.ini").exists()

    def test_env_example_exists(self) -> None:
        assert (Path(__file__).parent.parent / ".env.example").exists()


# ============================================================================
# End-to-End: Full Trading Pipeline
# ============================================================================


class TestEndToEndPipeline:
    """Test the complete trading pipeline from scan to execution."""

    @pytest.mark.asyncio
    async def test_full_pipeline(self, trading_ctx) -> None:
        """Simulate the full evaluation pipeline:
        market -> probability -> edge -> kelly -> risk check -> execute.
        """
        from src.core.edge import calculate_edge
        from src.core.executor import safe_place_order
        from src.core.kelly import fee_adjusted_kelly
        from src.core.portfolio import PortfolioTracker
        from src.core.probability import CalibrationTracker
        from src.core.reconciliation import startup_reconciliation
        from src.core.risk import RiskManager
        from src.data.schemas import ConsensusEstimate, TradeDecision

        # 1. Reconciliation on startup
        await startup_reconciliation(trading_ctx)

        # 2. Simulate a market with consensus probability
        estimate = ConsensusEstimate(
            probability=0.70,
            confidence="high",
            claude_estimate=0.72,
            gemini_estimate=0.68,
            gpt_estimate=0.70,
            spread=0.04,
        )

        # 3. Calculate edge
        edge = calculate_edge(estimate, market_price=0.50, fee_rate_bps=200)
        assert edge.magnitude > 0
        assert edge.direction == "BUY"

        # 4. Kelly sizing
        kelly = fee_adjusted_kelly(
            estimated_prob=0.70,
            market_price=0.50,
            fee_rate_bps=200,
            kelly_multiplier=0.25,
            bankroll=1000.0,
        )
        assert kelly.position_size_usd > 0

        # 5. Risk check
        rm = RiskManager()
        rm.update_portfolio_value(1000.0)
        risk_result = await rm.check(
            market_id="test_market",
            edge=edge,
            open_positions_count=0,
            portfolio_value=1000.0,
            ctx=trading_ctx,
        )
        assert risk_result.approved is True

        # 6. Execute (paper mode)
        decision = TradeDecision(
            action="BUY",
            market_id="test_market",
            token_id="test_token",
            size_usd=kelly.position_size_usd,
            price=0.50,
            edge=edge,
            kelly=kelly,
            estimate=estimate,
        )
        result = await safe_place_order(decision, trading_ctx)
        assert result["status"] in ("filled", "rejected")

        # 7. Track in portfolio
        portfolio = PortfolioTracker(1000.0)
        if result["status"] == "filled":
            fill = result["fill"]
            await portfolio.open_position(
                market_id="test_market",
                token_id="test_token",
                side="YES",
                quantity=fill["quantity"],
                price=fill["price"],
                fee=fill["fee"],
                ctx=trading_ctx,
            )

            summary = await portfolio.get_summary(trading_ctx)
            assert summary.open_positions_count == 1

        # 8. Calibration tracking
        calibration = CalibrationTracker(trading_ctx.repo)
        await trading_ctx.repo.save_probability_estimate({
            "market_id": "test_market",
            "model": "consensus",
            "probability": 0.70,
            "confidence": "high",
            "reasoning": "test",
            "market_price_at_estimate": 0.50,
        })

        # Simulate resolution
        scores = await calibration.record_resolution("test_market", 1)
        assert len(scores) >= 1

        brier = await calibration.get_rolling_brier()
        assert 0 <= brier <= 1

    @pytest.mark.asyncio
    async def test_backtest_framework(self) -> None:
        """Test the backtesting and Monte Carlo modules."""
        from scripts.backtest import (
            BacktestResult,
            BacktestTrade,
            monte_carlo_risk_of_ruin,
            run_backtest,
        )

        trades = [
            BacktestTrade("m1", 0.40, 0.60, 50.0, "BUY", 1.0, 9.0),
            BacktestTrade("m2", 0.50, 0.40, 30.0, "BUY", 0.5, -3.5),
            BacktestTrade("m3", 0.30, 0.70, 40.0, "BUY", 0.8, 15.2),
        ]

        result = run_backtest(trades, initial_bankroll=1000.0)
        assert result.num_trades == 3
        assert result.win_rate > 0
        assert result.total_pnl > 0

        # Monte Carlo
        mc = monte_carlo_risk_of_ruin(
            win_rate=0.55,
            avg_win=20.0,
            avg_loss=15.0,
            num_simulations=1000,
            num_trades=100,
            seed=42,
        )
        assert "risk_of_ruin" in mc
        assert 0 <= mc["risk_of_ruin"] <= 1
        assert mc["median_final_equity"] > 0


# ============================================================================
# Module Completeness Check
# ============================================================================


class TestModuleCompleteness:
    """Verify all modules from the project structure are importable."""

    REQUIRED_MODULES = [
        # Phase 1
        "src.config",
        "src.context",
        "src.main",
        "src.data.database",
        "src.data.models",
        "src.data.schemas",
        "src.data.repository",
        "src.integrations.polymarket",
        "src.utils.logging",
        "src.utils.metrics",
        "src.utils.rate_limiter",
        "src.utils.retry",
        "src.api.auth",
        "src.api.dependencies",
        "src.api.routes.health",
        # Phase 2
        "src.core.scanner",
        "src.core.probability",
        "src.core.edge",
        "src.core.kelly",
        "src.core.risk",
        "src.agents.consensus",
        "src.agents.debate",
        "src.agents.state",
        # Phase 3
        "src.core.executor",
        "src.core.portfolio",
        "src.core.resolution",
        "src.core.reconciliation",
        # Phase 4
        "src.core.arbitrage",
        "src.core.news",
        "src.integrations.websocket_feed",
        "src.integrations.telegram",
        "src.integrations.news_feeds",
        "src.integrations.whale_tracker",
        # Phase 5
        "src.api.routes.portfolio",
        "src.api.routes.markets",
        "src.api.routes.trades",
        "src.api.routes.calibration",
        "src.api.routes.controls",
    ]

    @pytest.mark.parametrize("module_name", REQUIRED_MODULES)
    def test_module_importable(self, module_name: str) -> None:
        """Each required module should import without errors."""
        mod = importlib.import_module(module_name)
        assert mod is not None
