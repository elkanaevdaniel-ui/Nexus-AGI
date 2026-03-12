"""Twitter/X signal collector — monitors tweets for prediction market signals."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import httpx
from loguru import logger

from src.signals.types import Signal

if TYPE_CHECKING:
    from src.context import TradingContext

_SEARCH_URL = "https://api.twitter.com/2/tweets/search/recent"


class TwitterCollector:
    """Collects signals from Twitter/X via the v2 API (Basic tier)."""

    async def collect(
        self,
        keywords: list[str],
        ctx: TradingContext,
        max_results: int = 20,
    ) -> list[Signal]:
        """Search recent tweets matching keywords.

        Args:
            keywords: Search terms from market question.
            ctx: Trading context.
            max_results: Max tweets to fetch (10-100).
        """
        bearer = ctx.config.twitter_bearer_token.get_secret_value()
        if not bearer:
            logger.debug("Twitter: no bearer token configured, skipping")
            return []

        # Build query: keywords + filter out retweets and replies
        query_terms = " OR ".join(f'"{k}"' for k in keywords[:3])
        query = f"({query_terms}) -is:retweet -is:reply lang:en"

        # Cap query to Twitter's 512-char limit
        if len(query) > 512:
            query = query[:509] + "..."

        signals: list[Signal] = []

        try:
            async with httpx.AsyncClient(timeout=15.0) as http:
                resp = await http.get(
                    _SEARCH_URL,
                    params={
                        "query": query,
                        "max_results": min(max_results, 100),
                        "tweet.fields": "created_at,public_metrics,author_id",
                        "sort_order": "relevancy",
                    },
                    headers={"Authorization": f"Bearer {bearer}"},
                )

                if resp.status_code == 429:
                    logger.warning("Twitter rate limited")
                    return []

                resp.raise_for_status()
                data = resp.json()

                for tweet in data.get("data", []):
                    metrics = tweet.get("public_metrics", {})
                    likes = metrics.get("like_count", 0)
                    retweets = metrics.get("retweet_count", 0)
                    replies = metrics.get("reply_count", 0)

                    # Engagement-based relevance
                    engagement = likes + retweets * 3 + replies * 2
                    relevance = min(1.0, engagement / 1000)

                    # Sentiment is left at 0 (neutral) — real sentiment
                    # analysis happens in the LLM pipeline when it reads
                    # the aggregated signal context
                    created = tweet.get("created_at", "")
                    try:
                        pub_at = datetime.fromisoformat(
                            created.replace("Z", "+00:00")
                        )
                    except (ValueError, AttributeError):
                        pub_at = datetime.now(timezone.utc)

                    tweet_id = tweet.get("id", "")
                    signals.append(
                        Signal(
                            source="twitter",
                            title=tweet.get("text", "")[:300],
                            url=f"https://x.com/i/status/{tweet_id}" if tweet_id else "",
                            published_at=pub_at,
                            sentiment=0.0,  # LLM will interpret
                            relevance=round(relevance, 3),
                            metadata={
                                "likes": likes,
                                "retweets": retweets,
                                "replies": replies,
                                "author_id": tweet.get("author_id", ""),
                            },
                        )
                    )

        except Exception as e:
            logger.warning(f"Twitter search failed: {e}")

        logger.info(f"Twitter: collected {len(signals)} signals")
        return signals
