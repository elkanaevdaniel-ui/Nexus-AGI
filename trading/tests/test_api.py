"""Tests for all API endpoints (health, portfolio, markets, controls, calibration)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.auth import create_access_token
from src.context import TradingContext
from src.main import create_app

_JWT_SECRET = "test_jwt_secret_for_testing_only"


def _auth_headers(role: str = "viewer") -> dict[str, str]:
    token = create_access_token("test_user", _JWT_SECRET, role=role)
    return {"Authorization": f"Bearer {token}"}


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    @pytest.fixture
    def client(self, trading_ctx: TradingContext) -> TestClient:
        app = create_app()
        app.state.trading_ctx = trading_ctx
        return TestClient(app, raise_server_exceptions=False)

    def test_health_returns_200(
        self, client: TestClient, trading_ctx: TradingContext
    ) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["trading_mode"] == "paper"
        assert data["trading_paused"] is False
        assert data["uptime_seconds"] >= 0

    def test_health_shows_paused_state(
        self, trading_ctx: TradingContext
    ) -> None:
        trading_ctx.trading_paused = True
        app = create_app()
        app.state.trading_ctx = trading_ctx
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/health")
        assert response.json()["trading_paused"] is True
        trading_ctx.trading_paused = False


class TestPortfolioEndpoints:
    """Tests for portfolio API."""

    @pytest.fixture
    def client(self, trading_ctx: TradingContext) -> TestClient:
        app = create_app()
        app.state.trading_ctx = trading_ctx
        return TestClient(app, raise_server_exceptions=False)

    def test_portfolio_summary(self, client: TestClient) -> None:
        response = client.get(
            "/api/portfolio/summary", headers=_auth_headers()
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_value" in data
        assert "cash_balance" in data

    def test_positions_empty(self, client: TestClient) -> None:
        response = client.get(
            "/api/portfolio/positions", headers=_auth_headers()
        )
        assert response.status_code == 200
        assert response.json() == []

    def test_portfolio_requires_auth(self, client: TestClient) -> None:
        response = client.get("/api/portfolio/summary")
        assert response.status_code == 401


class TestMarketEndpoints:
    """Tests for market API."""

    @pytest.fixture
    def client(self, trading_ctx: TradingContext) -> TestClient:
        app = create_app()
        app.state.trading_ctx = trading_ctx
        return TestClient(app, raise_server_exceptions=False)

    def test_list_markets_empty(self, client: TestClient) -> None:
        response = client.get("/api/markets/", headers=_auth_headers())
        assert response.status_code == 200
        assert response.json() == []

    def test_get_nonexistent_market(self, client: TestClient) -> None:
        response = client.get(
            "/api/markets/nonexistent", headers=_auth_headers()
        )
        assert response.status_code == 404

    def test_markets_requires_auth(self, client: TestClient) -> None:
        response = client.get("/api/markets/")
        assert response.status_code == 401

    def test_invalid_market_id_rejected(self, client: TestClient) -> None:
        response = client.get(
            "/api/markets/invalid%20market%3Bid!@#", headers=_auth_headers()
        )
        assert response.status_code == 422


class TestControlEndpoints:
    """Tests for trading control API."""

    _JWT_SECRET = "test_jwt_secret_for_testing_only"

    @pytest.fixture
    def client(self, trading_ctx: TradingContext) -> TestClient:
        app = create_app()
        app.state.trading_ctx = trading_ctx
        return TestClient(app, raise_server_exceptions=False)

    def _op_headers(self, role: str = "operator") -> dict[str, str]:
        token = create_access_token("test_user", self._JWT_SECRET, role=role)
        return {"Authorization": f"Bearer {token}"}

    def test_get_trading_state(self, client: TestClient) -> None:
        response = client.get(
            "/api/controls/state", headers=self._op_headers("viewer")
        )
        assert response.status_code == 200
        data = response.json()
        assert "trading_paused" in data
        assert "trading_mode" in data

    def test_pause_trading(
        self, client: TestClient, trading_ctx: TradingContext
    ) -> None:
        trading_ctx.trading_paused = False
        response = client.post(
            "/api/controls/trading",
            json={"action": "pause", "reason": "test"},
            headers=self._op_headers(),
        )
        assert response.status_code == 200
        assert response.json()["trading_paused"] is True

    def test_resume_trading(
        self, client: TestClient, trading_ctx: TradingContext
    ) -> None:
        trading_ctx.trading_paused = True
        response = client.post(
            "/api/controls/trading",
            json={"action": "resume"},
            headers=self._op_headers(),
        )
        assert response.status_code == 200
        assert response.json()["trading_paused"] is False

    def test_invalid_action(self, client: TestClient) -> None:
        response = client.post(
            "/api/controls/trading",
            json={"action": "invalid"},
            headers=self._op_headers(),
        )
        assert response.status_code == 400

    def test_update_config(self, client: TestClient) -> None:
        response = client.patch(
            "/api/controls/config",
            json={"kelly_fraction": 0.30},
            headers=self._op_headers(),
        )
        assert response.status_code == 200
        assert "updated" in response.json()

    def test_cancel_all_no_clob(
        self, client: TestClient, trading_ctx: TradingContext
    ) -> None:
        trading_ctx.clob = None
        response = client.post(
            "/api/controls/cancel-all",
            headers=self._op_headers(),
        )
        assert response.status_code == 200
        assert response.json()["status"] == "no_clob_client"

    def test_unauthenticated_returns_401(self, client: TestClient) -> None:
        response = client.get("/api/controls/state")
        assert response.status_code == 401

    def test_viewer_cannot_pause(self, client: TestClient) -> None:
        response = client.post(
            "/api/controls/trading",
            json={"action": "pause"},
            headers=self._op_headers("viewer"),
        )
        assert response.status_code == 403


class TestCalibrationEndpoint:
    """Tests for calibration API."""

    @pytest.fixture
    def client(self, trading_ctx: TradingContext) -> TestClient:
        app = create_app()
        app.state.trading_ctx = trading_ctx
        return TestClient(app, raise_server_exceptions=False)

    def test_get_calibration(self, client: TestClient) -> None:
        response = client.get("/api/calibration/", headers=_auth_headers())
        assert response.status_code == 200
        data = response.json()
        assert "rolling_brier_score" in data
        assert data["rolling_brier_score"] == 0.25  # Default when no data

    def test_calibration_requires_auth(self, client: TestClient) -> None:
        response = client.get("/api/calibration/")
        assert response.status_code == 401


class TestJWTAuth:
    """Tests for JWT token creation and validation."""

    def test_create_and_decode_token(self) -> None:
        from src.api.auth import create_access_token, decode_token

        secret = "test_secret_key"
        token = create_access_token("admin", secret, role="admin")
        payload = decode_token(token, secret)
        assert payload is not None
        assert payload.sub == "admin"
        assert payload.role == "admin"

    def test_invalid_token_returns_none(self) -> None:
        from src.api.auth import decode_token

        payload = decode_token("invalid_token", "secret")
        assert payload is None

    def test_wrong_secret_returns_none(self) -> None:
        from src.api.auth import create_access_token, decode_token

        token = create_access_token("user", "correct_secret")
        payload = decode_token(token, "wrong_secret")
        assert payload is None
