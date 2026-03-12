"""Exponential backoff retry with idempotency support."""

from __future__ import annotations

import asyncio
import functools
from typing import Any, Callable, TypeVar

from loguru import logger

T = TypeVar("T")


def async_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable:
    """Decorator for async functions with exponential backoff retry."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = min(
                            base_delay * (backoff_factor ** attempt),
                            max_delay,
                        )
                        logger.warning(
                            f"Retry {attempt + 1}/{max_retries} for "
                            f"{func.__name__}: {e}. "
                            f"Waiting {delay:.1f}s"
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"All {max_retries} retries exhausted for "
                            f"{func.__name__}: {e}"
                        )
            raise last_exception  # type: ignore[misc]

        return wrapper

    return decorator
