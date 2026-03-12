"""TradingContext — dependency injection container for the trading engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from src.config import DynamicConfig, StaticConfig
from src.data.repository import Repository
from src.integrations.polymarket import AsyncClobWrapper, GammaClient

if TYPE_CHECKING:
    from src.core.portfolio import PortfolioTracker
    from src.core.probability import CalibrationTracker
    from src.core.risk import RiskManager
    from src.integrations.telegram import TelegramBot


@dataclass
class TradingContext:
    """Central context object passed to all trading components.

    Acts as a dependency injection container, holding references to
    config, database, API clients, and runtime state.
    """

    # Configuration
    config: StaticConfig
    dynamic_config: DynamicConfig

    # Data layer
    repo: Repository

    # API clients
    gamma: GammaClient
    clob: Optional[AsyncClobWrapper] = None

    # Core components (set after construction)
    portfolio: Optional[PortfolioTracker] = None
    risk_manager: Optional[RiskManager] = None
    calibration_tracker: Optional[CalibrationTracker] = None

    # Integrations
    telegram: Optional[TelegramBot] = None

    # Runtime state
    trading_paused: bool = True
    startup_time: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # Monitored token IDs for WebSocket subscriptions
    monitored_token_ids: list[str] = field(default_factory=list)

    @property
    def is_paper(self) -> bool:
        """Whether we're in paper trading mode."""
        return self.config.trading_mode == "paper"

    @property
    def is_live(self) -> bool:
        """Whether we're in live trading mode."""
        return self.config.trading_mode == "live"

    @property
    def uptime_seconds(self) -> float:
        """Seconds since startup."""
        return (datetime.now(timezone.utc) - self.startup_time).total_seconds()
