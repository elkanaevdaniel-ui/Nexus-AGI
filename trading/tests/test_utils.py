"""Tests for utility modules — logging, rate limiter, retry."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import patch

import pytest

from src.utils.logging import _redact
from src.utils.rate_limiter import TokenBucketRateLimiter
from src.utils.retry import async_retry


class TestSecretRedaction:
    """Tests for log secret redaction."""

    def test_redacts_wallet_address(self) -> None:
        """Should redact hex strings that look like wallet addresses."""
        msg = "Sending to 0x1234567890abcdef1234567890abcdef12345678"
        redacted = _redact(msg)
        assert "0x1234567890" not in redacted
        assert "[REDACTED]" in redacted

    def test_redacts_openai_key(self) -> None:
        """Should redact OpenAI-style API keys."""
        msg = "Using key sk-abcdefghij1234567890xyz"
        redacted = _redact(msg)
        assert "sk-abcdefghij" not in redacted

    def test_redacts_google_key(self) -> None:
        """Should redact Google API keys."""
        msg = "Google key AIzaSyC_abcdefghijklmnopqrstuvwxyz123456"
        redacted = _redact(msg)
        assert "AIzaSyC_" not in redacted

    def test_preserves_normal_text(self) -> None:
        """Should not redact normal log messages."""
        msg = "Market m1 has price 0.55 and volume 50000"
        redacted = _redact(msg)
        assert redacted == msg


class TestTokenBucketRateLimiter:
    """Tests for rate limiter."""

    @pytest.mark.asyncio
    async def test_allows_burst(self) -> None:
        """Should allow burst of requests up to bucket size."""
        limiter = TokenBucketRateLimiter(rate=10.0, burst=5)
        # Should be able to acquire 5 tokens immediately
        for _ in range(5):
            await limiter.acquire()

    @pytest.mark.asyncio
    async def test_throttles_after_burst(self) -> None:
        """Should throttle requests after burst is consumed."""
        limiter = TokenBucketRateLimiter(rate=100.0, burst=2)
        # Consume burst
        await limiter.acquire()
        await limiter.acquire()
        # Next should require waiting (but with rate=100, very brief)
        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start
        # With rate=100/s, should wait ~0.01s
        assert elapsed < 0.5  # Generous upper bound for CI


class TestAsyncRetry:
    """Tests for retry decorator."""

    @pytest.mark.asyncio
    async def test_succeeds_first_try(self) -> None:
        """Should return immediately on success."""
        call_count = 0

        @async_retry(max_retries=3, base_delay=0.01)
        async def succeed() -> str:
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await succeed()
        assert result == "ok"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_failure(self) -> None:
        """Should retry up to max_retries on failure."""
        call_count = 0

        @async_retry(max_retries=2, base_delay=0.01)
        async def fail_twice() -> str:
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ValueError("transient error")
            return "ok"

        result = await fail_twice()
        assert result == "ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_raises_after_exhausted(self) -> None:
        """Should raise last exception after retries exhausted."""

        @async_retry(max_retries=2, base_delay=0.01)
        async def always_fail() -> str:
            raise ValueError("permanent error")

        with pytest.raises(ValueError, match="permanent error"):
            await always_fail()

    @pytest.mark.asyncio
    async def test_only_retries_specified_exceptions(self) -> None:
        """Should not retry on unspecified exception types."""

        @async_retry(
            max_retries=3,
            base_delay=0.01,
            retryable_exceptions=(ConnectionError,),
        )
        async def wrong_error() -> str:
            raise ValueError("not retryable")

        with pytest.raises(ValueError):
            await wrong_error()
