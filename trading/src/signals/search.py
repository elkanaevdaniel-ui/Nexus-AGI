"""SerpAPI (Google Search) signal collector — real-time search for fact-checking."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import httpx
from loguru import logger

from src.signals.types import Signal

if TYPE_CHECKING:
    from src.context import TradingContext

_SERP_URL = "https://serpapi.com/search.json"


class SearchCollector:
    """Collects signals from Google Search via SerpAPI.

    This is the most important signal source for fact-checking claims
    and finding recent evidence relevant to market questions.
    """

    async def collect(
        self,
        query: str,
        ctx: TradingContext,
        num_results: int = 10,
    ) -> list[Signal]:
        """Search Google for recent results related to a market question.

        Args:
            query: The market question or derived search query.
            ctx: Trading context.
            num_results: Number of results to fetch.
        """
        api_key = ctx.config.serp_api_key.get_secret_value()
        if not api_key:
            logger.debug("SerpAPI: no key configured, skipping")
            return []

        signals: list[Signal] = []

        try:
            async with httpx.AsyncClient(timeout=20.0) as http:
                # Regular web search
                resp = await http.get(
                    _SERP_URL,
                    params={
                        "api_key": api_key,
                        "q": query[:200],
                        "num": num_results,
                        "engine": "google",
                        "gl": "us",
                        "hl": "en",
                        "tbm": "",  # Web search
                        "tbs": "qdr:w",  # Past week
                    },
                )
                resp.raise_for_status()
                data = resp.json()

                # Organic results
                for i, result in enumerate(data.get("organic_results", [])):
                    position_relevance = max(0.1, 1.0 - (i * 0.1))

                    signals.append(
                        Signal(
                            source="search",
                            title=result.get("title", "")[:300],
                            body=result.get("snippet", "")[:500],
                            url=result.get("link", ""),
                            published_at=_parse_date(result.get("date", "")),
                            sentiment=0.0,  # LLM interprets
                            relevance=round(position_relevance, 3),
                            metadata={
                                "position": i + 1,
                                "source_domain": result.get("displayed_link", ""),
                            },
                        )
                    )

                # Knowledge graph (if present — quick facts)
                kg = data.get("knowledge_graph", {})
                if kg and kg.get("description"):
                    signals.append(
                        Signal(
                            source="search",
                            title=kg.get("title", "Knowledge Graph"),
                            body=kg.get("description", "")[:500],
                            url=kg.get("website", ""),
                            published_at=datetime.now(timezone.utc),
                            sentiment=0.0,
                            relevance=0.9,
                            metadata={"type": "knowledge_graph"},
                        )
                    )

                # News results (if Google returns inline news)
                for news in data.get("news_results", []):
                    signals.append(
                        Signal(
                            source="search",
                            title=news.get("title", "")[:300],
                            body=news.get("snippet", "")[:500],
                            url=news.get("link", ""),
                            published_at=_parse_date(news.get("date", "")),
                            sentiment=0.0,
                            relevance=0.8,
                            metadata={
                                "type": "news_inline",
                                "source": news.get("source", {}).get("name", ""),
                            },
                        )
                    )

        except Exception as e:
            logger.warning(f"SerpAPI search failed: {e}")

        logger.info(f"Search: collected {len(signals)} signals for '{query[:50]}'")
        return signals

    async def collect_news(
        self,
        query: str,
        ctx: TradingContext,
        num_results: int = 10,
    ) -> list[Signal]:
        """Google News search for a market question."""
        api_key = ctx.config.serp_api_key.get_secret_value()
        if not api_key:
            return []

        signals: list[Signal] = []

        try:
            async with httpx.AsyncClient(timeout=20.0) as http:
                resp = await http.get(
                    _SERP_URL,
                    params={
                        "api_key": api_key,
                        "q": query[:200],
                        "num": num_results,
                        "engine": "google_news",
                        "gl": "us",
                        "hl": "en",
                    },
                )
                resp.raise_for_status()
                data = resp.json()

                for i, article in enumerate(data.get("news_results", [])):
                    position_relevance = max(0.2, 1.0 - (i * 0.08))
                    signals.append(
                        Signal(
                            source="news",
                            title=article.get("title", "")[:300],
                            body=article.get("snippet", "")[:500],
                            url=article.get("link", ""),
                            published_at=_parse_date(article.get("date", "")),
                            sentiment=0.0,
                            relevance=round(position_relevance, 3),
                            metadata={
                                "source": article.get("source", {}).get("name", ""),
                                "type": "google_news",
                            },
                        )
                    )

        except Exception as e:
            logger.warning(f"SerpAPI news search failed: {e}")

        return signals


def _parse_date(date_str: str) -> datetime:
    """Best-effort parse of various date formats from search results."""
    if not date_str:
        return datetime.now(timezone.utc)
    try:
        # SerpAPI often returns relative dates like "2 hours ago", "3 days ago"
        lower = date_str.lower()
        now = datetime.now(timezone.utc)
        if "hour" in lower:
            hours = int("".join(c for c in lower if c.isdigit()) or "1")
            from datetime import timedelta
            return now - timedelta(hours=hours)
        if "day" in lower:
            days = int("".join(c for c in lower if c.isdigit()) or "1")
            from datetime import timedelta
            return now - timedelta(days=days)
        if "minute" in lower:
            mins = int("".join(c for c in lower if c.isdigit()) or "1")
            from datetime import timedelta
            return now - timedelta(minutes=mins)
        # Try ISO
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return datetime.now(timezone.utc)
