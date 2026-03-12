"""Loguru configuration with secret redaction filter."""

from __future__ import annotations

import re
import sys

from loguru import logger

# Patterns to redact from logs
_REDACT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"0x[a-fA-F0-9]{40,}"),  # Wallet addresses / private keys
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),  # OpenAI-style API keys
    re.compile(r"sk-ant-[a-zA-Z0-9_-]{20,}"),  # Anthropic API keys
    re.compile(r"key-[a-zA-Z0-9]{20,}"),  # Generic API keys
    re.compile(r"AIza[a-zA-Z0-9_-]{35}"),  # Google API keys
    re.compile(r"\b\d{6,}:[a-zA-Z0-9_-]{20,}"),  # Telegram bot tokens
    re.compile(r"eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}"),  # JWT tokens
    re.compile(r"(?:secret|password|token|key)=[^\s&]+", re.IGNORECASE),
    re.compile(r"redis://[^\s]*:[^\s@]+@", re.IGNORECASE),  # Redis connection strings
    re.compile(r"postgresql://[^\s]*:[^\s@]+@", re.IGNORECASE),  # PostgreSQL connection strings
    re.compile(r"mongodb://[^\s]*:[^\s@]+@", re.IGNORECASE),  # MongoDB connection strings
    re.compile(r"Bearer\s+[a-zA-Z0-9_\-.]+", re.IGNORECASE),  # Bearer tokens in headers
]


def _redact(message: str) -> str:
    """Replace sensitive patterns with [REDACTED]."""
    for pattern in _REDACT_PATTERNS:
        message = pattern.sub("[REDACTED]", message)
    return message


def _redaction_filter(record: dict) -> bool:
    """Loguru filter that redacts secrets from log messages."""
    record["message"] = _redact(record["message"])
    return True


def setup_logging(level: str = "INFO", json_format: bool = False) -> None:
    """Configure loguru with redaction and structured output."""
    logger.remove()

    fmt = (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | "
        "{name}:{function}:{line} | {message}"
    )
    if json_format:
        fmt = (
            '{{"timestamp":"{time:YYYY-MM-DDTHH:mm:ss.SSSZ}",'
            '"level":"{level}","logger":"{name}:{function}:{line}",'
            '"message":"{message}"}}'
        )

    logger.add(
        sys.stderr,
        format=fmt,
        level=level,
        filter=_redaction_filter,
        colorize=not json_format,
    )

    logger.add(
        "logs/trading.log",
        format=fmt,
        level=level,
        filter=_redaction_filter,
        rotation="50 MB",
        retention="30 days",
        compression="gz",
    )
