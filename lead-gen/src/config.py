"""Lead Gen service configuration — reads from root .env."""

from pathlib import Path
from pydantic_settings import BaseSettings


def _find_root_env() -> str | None:
    """Walk up from this file to find the root .env."""
    current = Path(__file__).resolve().parent
    for _ in range(5):
        candidate = current / ".env"
        if candidate.exists():
            return str(candidate)
        current = current.parent
    return None


class Settings(BaseSettings):
    # Apollo.io
    apollo_api_key: str = ""

    # Shared LLM keys (from root .env)
    anthropic_api_key: str = ""
    openrouter_api_key: str = ""

    # Service
    lead_gen_port: int = 8082
    lead_gen_db_url: str = "sqlite:///./lead_gen.db"
    command_center_api_key: str = ""

    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:3001,https://nexus-elkana.duckdns.org"

    # ICP defaults
    default_icp_industry: str = "technology"
    default_icp_min_employees: int = 10
    default_icp_max_employees: int = 1000
    default_icp_seniority: str = "director,vp,c_suite,founder"

    # Outreach
    outreach_daily_limit: int = 50
    outreach_delay_seconds: int = 60

    # LLM
    llm_model: str = "anthropic/claude-3-haiku"

    model_config = {
        "env_file": _find_root_env() or ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
