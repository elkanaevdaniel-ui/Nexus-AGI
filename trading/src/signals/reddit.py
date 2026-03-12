"""Reddit signal collector — monitors subreddits for prediction market signals."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import httpx
from loguru import logger

from src.signals.types import Signal

if TYPE_CHECKING:
    from src.context import TradingContext

# Subreddits most relevant to Polymarket categories
_SUBREDDITS = [
    "polymarket",
    "prediction",
    "politics",
    "worldnews",
    "cryptocurrency",
    "bitcoin",
    "economics",
    "geopolitics",
    "sports",
    "technology",
]

_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
_API_BASE = "https://oauth.reddit.com"


class RedditCollector:
    """Collects signals from Reddit via the official API."""

    def __init__(self) -> None:
        self._access_token: str = ""
        self._token_expires: float = 0.0

    async def _authenticate(self, ctx: TradingContext) -> bool:
        """Get OAuth2 access token using app-only flow."""
        client_id = ctx.config.reddit_client_id
        client_secret = ctx.config.reddit_client_secret.get_secret_value()

        if not client_id or not client_secret:
            return False

        try:
            async with httpx.AsyncClient(timeout=10.0) as http:
                resp = await http.post(
                    _TOKEN_URL,
                    data={"grant_type": "client_credentials"},
                    auth=(client_id, client_secret),
                    headers={"User-Agent": ctx.config.reddit_user_agent},
                )
                resp.raise_for_status()
                data = resp.json()
                self._access_token = data["access_token"]
                self._token_expires = (
                    datetime.now(timezone.utc).timestamp() + data.get("expires_in", 3600) - 60
                )
                return True
        except Exception as e:
            logger.warning(f"Reddit auth failed: {e}")
            return False

    async def _ensure_token(self, ctx: TradingContext) -> bool:
        """Ensure we have a valid access token."""
        if self._access_token and datetime.now(timezone.utc).timestamp() < self._token_expires:
            return True
        return await self._authenticate(ctx)

    async def collect(
        self,
        keywords: list[str],
        ctx: TradingContext,
        subreddits: list[str] | None = None,
        limit: int = 25,
    ) -> list[Signal]:
        """Search Reddit for posts matching keywords.

        Args:
            keywords: Search terms derived from market question.
            ctx: Trading context with config.
            subreddits: Override default subreddit list.
            limit: Max posts per subreddit.
        """
        if not await self._ensure_token(ctx):
            logger.debug("Reddit: no credentials configured, skipping")
            return []

        subs = subreddits or _SUBREDDITS
        query = " OR ".join(keywords[:5])  # Reddit search limit
        signals: list[Signal] = []

        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "User-Agent": ctx.config.reddit_user_agent,
        }

        async with httpx.AsyncClient(timeout=15.0, headers=headers) as http:
            for sub in subs[:5]:  # Cap to avoid rate limits
                try:
                    resp = await http.get(
                        f"{_API_BASE}/r/{sub}/search.json",
                        params={
                            "q": query,
                            "sort": "new",
                            "t": "day",  # Last 24 hours
                            "limit": limit,
                            "restrict_sr": "true",
                        },
                    )
                    if resp.status_code == 429:
                        logger.warning("Reddit rate limited, stopping")
                        break
                    resp.raise_for_status()

                    posts = resp.json().get("data", {}).get("children", [])
                    for post in posts:
                        d = post.get("data", {})
                        score = d.get("score", 0)
                        num_comments = d.get("num_comments", 0)

                        # Basic engagement-based relevance
                        engagement = min(1.0, (score + num_comments * 2) / 500)

                        # Upvote ratio as rough sentiment proxy
                        upvote_ratio = d.get("upvote_ratio", 0.5)
                        sentiment = (upvote_ratio - 0.5) * 2  # Map 0-1 → -1 to +1

                        created_utc = d.get("created_utc", 0)
                        signals.append(
                            Signal(
                                source="reddit",
                                title=d.get("title", "")[:300],
                                body=d.get("selftext", "")[:500],
                                url=f"https://reddit.com{d.get('permalink', '')}",
                                published_at=datetime.fromtimestamp(
                                    created_utc, tz=timezone.utc
                                ),
                                sentiment=round(sentiment, 3),
                                relevance=round(engagement, 3),
                                metadata={
                                    "subreddit": sub,
                                    "score": score,
                                    "num_comments": num_comments,
                                    "upvote_ratio": upvote_ratio,
                                },
                            )
                        )

                except Exception as e:
                    logger.warning(f"Reddit r/{sub} search failed: {e}")

        logger.info(f"Reddit: collected {len(signals)} signals for '{query[:50]}'")
        return signals
