"""Configuration management with static (env) and dynamic (runtime) settings."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings


class StaticConfig(BaseSettings):
    """Immutable config loaded at startup from env vars / .env file."""

    # Polymarket
    polymarket_private_key: SecretStr = SecretStr("")
    polymarket_proxy_address: str = ""
    polymarket_signature_type: int = 0  # 0=EOA, 1=Magic/email
    polymarket_host: str = "https://clob.polymarket.com"
    polymarket_chain_id: int = 137  # Polygon mainnet

    # LLM providers
    anthropic_api_key: SecretStr = SecretStr("")
    openai_api_key: SecretStr = SecretStr("")
    google_api_key: SecretStr = SecretStr("")
    openrouter_api_key: SecretStr = SecretStr("")

    # Infrastructure
    telegram_bot_token: SecretStr = SecretStr("")
    telegram_chat_id: str = ""
    database_url: str = "sqlite+aiosqlite:///./trading.db"
    redis_url: str = "redis://localhost:6379"
    news_api_key: SecretStr = SecretStr("")

    # Signal sources
    reddit_client_id: str = ""
    reddit_client_secret: SecretStr = SecretStr("")
    reddit_user_agent: str = "polymarket-agent/1.0"
    twitter_bearer_token: SecretStr = SecretStr("")
    serp_api_key: SecretStr = SecretStr("")

    # Security
    dashboard_jwt_secret: SecretStr = SecretStr("")
    dashboard_jwt_expire_minutes: int = 60

    # Trading
    trading_mode: str = "paper"  # paper or live
    initial_bankroll: Decimal = Decimal("100.0")

    # Gamma API
    gamma_api_url: str = "https://gamma-api.polymarket.com"

    # Agent Zero bridge
    agent_zero_url: str = "http://localhost:50001"
    agent_zero_api_key: SecretStr = SecretStr("")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


class DynamicConfig(BaseModel):
    """Mutable config, changeable via API at runtime. Persisted in Redis."""

    kelly_fraction: float = Field(0.5, ge=0.05, le=1.0)
    min_edge_threshold: float = Field(0.03, ge=0.02, le=0.20)
    max_daily_loss_pct: float = Field(1.0, ge=0.01, le=1.0)
    max_drawdown_pct: float = Field(1.0, ge=0.05, le=1.0)
    max_single_position_pct: float = Field(0.30, ge=0.01, le=0.50)
    max_open_positions: int = Field(10, ge=1, le=50)
    max_correlated_exposure_pct: float = Field(0.20, ge=0.05, le=0.40)
    scan_interval_seconds: int = Field(3600, ge=60, le=7200)
    min_market_volume: float = Field(1000.0, ge=100.0)
    min_market_liquidity: float = Field(500.0, ge=100.0)
    fee_rate_bps: int = Field(200, ge=0, le=500)  # Default 2% taker fee
    stop_loss_pct: float = Field(0.30, ge=0.05, le=1.0)  # Auto-sell at -30%
    analysis_model: str = Field("claude", description="LLM for analysis: claude, gemini, gpt, openrouter")
