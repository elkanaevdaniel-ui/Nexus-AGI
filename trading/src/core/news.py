"""News monitoring and event detection for market re-evaluation triggers."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

import httpx
from loguru import logger

if TYPE_CHECKING:
    from src.context import TradingContext


@dataclass(frozen=True)
class NewsEvent:
    """A detected news event that may impact markets."""

    title: str
    source: str
    url: str
    published_at: datetime
    relevance_score: float  # 0.0 to 1.0
    keywords: tuple[str, ...] = ()


_MAX_SEEN_URLS = 10_000


@dataclass
class NewsSentinel:
    """Monitors news feeds for events that could impact prediction markets."""

    _seen_urls: OrderedDict[str, None] = field(default_factory=OrderedDict)
    _last_check: Optional[datetime] = None

    async def check_news(
        self,
        ctx: TradingContext,
        keywords: Optional[list[str]] = None,
    ) -> list[NewsEvent]:
        """Check for new relevant news events.

        Uses NewsAPI if configured, otherwise returns empty.
        """
        api_key = ctx.config.news_api_key.get_secret_value()
        if not api_key:
            return []

        events: list[NewsEvent] = []

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                query_params: dict[str, str | int] = {
                    "language": "en",
                    "sortBy": "publishedAt",
                    "pageSize": 20,
                }

                if keywords:
                    query_params["q"] = " OR ".join(keywords)
                else:
                    query_params["q"] = "prediction market OR election OR crypto"

                response = await client.get(
                    "https://newsapi.org/v2/everything",
                    params=query_params,
                    headers={"X-Api-Key": api_key},
                )
                response.raise_for_status()
                data = response.json()

                for article in data.get("articles", []):
                    url = article.get("url", "")
                    if url in self._seen_urls:
                        continue

                    self._seen_urls[url] = None
                    # Evict oldest entries when cap is exceeded
                    while len(self._seen_urls) > _MAX_SEEN_URLS:
                        self._seen_urls.popitem(last=False)
                    try:
                        pub_at = datetime.fromisoformat(
                            article.get("publishedAt", "").replace("Z", "+00:00")
                        )
                    except (ValueError, AttributeError):
                        pub_at = datetime.now(timezone.utc)

                    events.append(
                        NewsEvent(
                            title=article.get("title", "")[:200],
                            source=article.get("source", {}).get("name", ""),
                            url=url,
                            published_at=pub_at,
                            relevance_score=0.5,
                        )
                    )

        except Exception as e:
            logger.warning(f"News check failed: {e}")

        self._last_check = datetime.now(timezone.utc)

        if events:
            logger.info(f"Found {len(events)} new news events")

        return events

    def match_markets(
        self,
        events: list[NewsEvent],
        market_questions: list[str],
    ) -> dict[str, list[NewsEvent]]:
        """Match news events to market questions by keyword overlap.

        Returns dict of market_question -> matching events.
        """
        matches: dict[str, list[NewsEvent]] = {}

        for question in market_questions:
            q_words = set(question.lower().split())
            matched = []
            for event in events:
                title_words = set(event.title.lower().split())
                overlap = q_words & title_words
                if len(overlap) >= 2:
                    matched.append(event)
            if matched:
                matches[question] = matched

        return matches
