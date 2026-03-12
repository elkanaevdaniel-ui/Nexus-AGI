"""JWT authentication middleware for the dashboard API.

Uses a pure-Python HMAC-SHA256 JWT implementation to avoid
dependency on the `cryptography` C extension (which may not be
available in all environments). For production, swap to
python-jose[cryptography] or PyJWT.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

security = HTTPBearer(auto_error=False)

_MIN_JWT_SECRET_LENGTH = 32


class TokenPayload(BaseModel):
    """JWT token payload."""

    sub: str  # Subject (username)
    exp: datetime  # Expiration
    role: str = "viewer"  # viewer, operator, admin


def validate_jwt_secret(secret: str) -> None:
    """Validate JWT secret meets minimum security requirements.

    Raises ValueError if secret is empty, too short, or a known test value.
    """
    if not secret:
        raise ValueError(
            "DASHBOARD_JWT_SECRET is not set. "
            "Generate one with: openssl rand -hex 32"
        )
    if len(secret) < _MIN_JWT_SECRET_LENGTH:
        raise ValueError(
            f"DASHBOARD_JWT_SECRET must be at least {_MIN_JWT_SECRET_LENGTH} "
            f"characters (got {len(secret)}). Generate with: openssl rand -hex 32"
        )


def _b64url_encode(data: bytes) -> str:
    """Base64url encode without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    """Base64url decode with padding restoration."""
    s += "=" * (4 - len(s) % 4)
    return base64.urlsafe_b64decode(s.encode("ascii"))


def create_access_token(
    subject: str,
    secret: str,
    expire_minutes: int = 60,
    role: str = "viewer",
) -> str:
    """Create a JWT access token (HMAC-SHA256)."""
    header = {"alg": "HS256", "typ": "JWT"}
    expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    payload = {
        "sub": subject,
        "exp": int(expire.timestamp()),
        "role": role,
    }

    header_b64 = _b64url_encode(json.dumps(header).encode())
    payload_b64 = _b64url_encode(json.dumps(payload).encode())
    signing_input = f"{header_b64}.{payload_b64}"

    signature = hmac.new(
        secret.encode(), signing_input.encode(), hashlib.sha256
    ).digest()
    sig_b64 = _b64url_encode(signature)

    return f"{header_b64}.{payload_b64}.{sig_b64}"


def decode_token(
    token: str,
    secret: str,
) -> Optional[TokenPayload]:
    """Decode and validate a JWT token (HMAC-SHA256)."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None

        header_b64, payload_b64, sig_b64 = parts

        # Verify signature (timing-safe comparison)
        signing_input = f"{header_b64}.{payload_b64}"
        expected_sig = hmac.new(
            secret.encode(), signing_input.encode(), hashlib.sha256
        ).digest()
        actual_sig = _b64url_decode(sig_b64)

        if not hmac.compare_digest(expected_sig, actual_sig):
            return None

        # Decode payload
        payload_json = _b64url_decode(payload_b64)
        payload = json.loads(payload_json)

        # Check expiration
        exp = payload.get("exp", 0)
        if exp < time.time():
            return None

        return TokenPayload(
            sub=payload["sub"],
            exp=datetime.fromtimestamp(exp, tz=timezone.utc),
            role=payload.get("role", "viewer"),
        )

    except Exception:
        return None


async def require_auth(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> TokenPayload:
    """Dependency that requires valid JWT auth (viewer+ role).

    Extracts the JWT secret from app state and actually validates the token.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    secret = request.app.state.trading_ctx.config.dashboard_jwt_secret.get_secret_value()
    payload = decode_token(credentials.credentials, secret)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


async def require_operator(
    payload: TokenPayload = Depends(require_auth),
) -> TokenPayload:
    """Dependency that requires operator or admin role."""
    if payload.role not in ("operator", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator or admin role required",
        )
    return payload


async def require_admin(
    payload: TokenPayload = Depends(require_auth),
) -> TokenPayload:
    """Dependency that requires admin role."""
    if payload.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return payload
