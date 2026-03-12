"""News API connectors for the News Sentinel."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx
from loguru import logger


@dataclass(frozen=True)
class NewsArticle:
    """A news article from any source."""

    title: str
    url: str
    source: str
    published_at: datetime
    description: str = ""


class NewsAPIClient:
    """Client for NewsAPI.org."""

    BASE_URL = "https://newsapi.org/v2"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._enabled = bool(api_key)

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def search(
        self,
        query: str,
        page_size: int = 20,
        language: str = "en",
    ) -> list[NewsArticle]:
        """Search for news articles."""
        if not self._enabled:
            return []

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/everything",
                    params={
                        "apiKey": self._api_key,
                        "q": query,
                        "language": language,
                        "sortBy": "publishedAt",
                        "pageSize": page_size,
                    },
                )
                response.raise_for_status()
                data = response.json()

                articles: list[NewsArticle] = []
                for item in data.get("articles", []):
                    try:
                        pub_at = datetime.fromisoformat(
                            item.get("publishedAt", "").replace("Z", "+00:00")
                        )
                    except (ValueError, AttributeError):
                        pub_at = datetime.now(timezone.utc)

                    articles.append(
                        NewsArticle(
                            title=item.get("title", "")[:200],
                            url=item.get("url", ""),
                            source=item.get("source", {}).get("name", ""),
                            published_at=pub_at,
                            description=item.get("description", "")[:500],
                        )
                    )
                return articles

        except Exception as e:
            logger.warning(f"NewsAPI search failed: {e}")
            return []


class RSSFeedReader:
    """Simple RSS/Atom feed reader for news monitoring."""

    def __init__(self) -> None:
        self._feeds: list[str] = []

    def add_feed(self, url: str) -> None:
        """Add an RSS feed URL to monitor."""
        self._feeds.append(url)

    async def fetch_latest(self, limit: int = 10) -> list[NewsArticle]:
        """Fetch latest articles from all configured feeds.

        Note: Requires `feedparser` for production. Falls back to empty
        in sandbox/test environments.
        """
        articles: list[NewsArticle] = []

        for feed_url in self._feeds:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(feed_url)
                    response.raise_for_status()
                    # Basic XML parsing fallback
                    # In production, use feedparser
                    logger.debug(f"Fetched RSS feed: {feed_url}")
            except Exception as e:
                logger.warning(f"RSS fetch failed for {feed_url}: {e}")

        return articles[:limit]
