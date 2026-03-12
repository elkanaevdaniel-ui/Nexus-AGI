"""API key authentication for Lead Gen service."""

import hmac

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from src.config import settings

_api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)


async def verify_api_key(
    api_key: str | None = Security(_api_key_header),
) -> str:
    """Validate the API key from the request header.

    Fails closed: if no API key is configured, all requests are rejected.
    Uses constant-time comparison to prevent timing attacks.
    """
    if not settings.command_center_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server misconfigured: no API key set. Set COMMAND_CENTER_API_KEY.",
        )
    if not api_key or not hmac.compare_digest(
        api_key.encode(), settings.command_center_api_key.encode()
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return api_key
