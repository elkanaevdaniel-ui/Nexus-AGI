"""Token bucket rate limiter for API calls."""

from __future__ import annotations

import asyncio
import time


class TokenBucketRateLimiter:
    """Async token bucket rate limiter.

    Enforces a maximum rate of requests per second using the token bucket
    algorithm. The lock is released during sleep to avoid convoy effect.
    """

    def __init__(
        self,
        rate: float = 10.0,
        burst: int = 20,
    ) -> None:
        self._rate = rate  # Tokens per second
        self._burst = burst  # Max tokens in bucket
        self._tokens = float(burst)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> None:
        """Wait until the requested number of tokens are available.

        Releases the lock while sleeping so other coroutines can proceed.
        """
        while True:
            async with self._lock:
                self._refill()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                # Calculate wait time — lock is released before sleep
                deficit = tokens - self._tokens
                wait_time = deficit / self._rate

            # Sleep OUTSIDE the lock so others can acquire
            await asyncio.sleep(wait_time)

    def _refill(self) -> None:
        """Add tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(
            self._burst,
            self._tokens + elapsed * self._rate,
        )
        self._last_refill = now
