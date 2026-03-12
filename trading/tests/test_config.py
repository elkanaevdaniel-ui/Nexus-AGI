"""Tests for configuration module."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.config import DynamicConfig, StaticConfig


class TestStaticConfig:
    """Tests for StaticConfig."""

    def test_defaults(self) -> None:
        """Static config should have sane defaults."""
        config = StaticConfig(
            polymarket_private_key="test_key",
            dashboard_jwt_secret="test_secret",
        )
        assert config.trading_mode == "paper"
        assert config.polymarket_chain_id == 137
        # initial_bankroll comes from .env (1000.0) or Python default (100.0)
        assert config.initial_bankroll in (100.0, 1000.0)
        assert config.database_url == "sqlite+aiosqlite:///./trading.db"

    def test_secret_str_masks_key(self) -> None:
        """SecretStr should not expose secrets in repr."""
        config = StaticConfig(
            polymarket_private_key="super_secret_key_123",
            dashboard_jwt_secret="jwt_secret",
        )
        repr_str = repr(config.polymarket_private_key)
        assert "super_secret_key_123" not in repr_str
        # But value is accessible via get_secret_value
        assert (
            config.polymarket_private_key.get_secret_value()
            == "super_secret_key_123"
        )


class TestDynamicConfig:
    """Tests for DynamicConfig."""

    def test_defaults(self) -> None:
        """Dynamic config should have paper-mode aggressive defaults."""
        config = DynamicConfig()
        assert config.kelly_fraction == 0.5
        assert config.min_edge_threshold == 0.03
        assert config.max_daily_loss_pct == 1.0
        assert config.max_drawdown_pct == 1.0
        assert config.max_single_position_pct == 0.30
        assert config.max_open_positions == 10
        assert config.fee_rate_bps == 200
        assert config.stop_loss_pct == 0.30
        assert config.analysis_model == "claude"

    def test_kelly_fraction_bounds(self) -> None:
        """Kelly fraction must be within [0.05, 1.0]."""
        config = DynamicConfig(kelly_fraction=0.1)
        assert config.kelly_fraction == 0.1

        with pytest.raises(ValidationError):
            DynamicConfig(kelly_fraction=0.01)  # Too low

        with pytest.raises(ValidationError):
            DynamicConfig(kelly_fraction=1.5)  # Too high

    def test_edge_threshold_bounds(self) -> None:
        """Edge threshold must be within [0.02, 0.20]."""
        with pytest.raises(ValidationError):
            DynamicConfig(min_edge_threshold=0.01)

        with pytest.raises(ValidationError):
            DynamicConfig(min_edge_threshold=0.25)

    def test_position_limits(self) -> None:
        """Position size limits must be reasonable."""
        with pytest.raises(ValidationError):
            DynamicConfig(max_single_position_pct=0.6)  # Too high (max 0.50)

        with pytest.raises(ValidationError):
            DynamicConfig(max_open_positions=51)  # Too many
