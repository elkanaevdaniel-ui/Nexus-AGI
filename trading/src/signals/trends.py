"""Google Trends signal — detects surging interest in market topics."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import httpx
from loguru import logger

from src.signals.types import Signal

if TYPE_CHECKING:
    from src.context import TradingContext

_SERP_TRENDS_URL = "https://serpapi.com/search.json"


class TrendsCollector:
    """Collects Google Trends data via SerpAPI.

    Detects surging interest in topics — a leading indicator that
    a market may be about to move as more attention drives price discovery.
    """

    async def collect(
        self,
        keywords: list[str],
        ctx: TradingContext,
    ) -> list[Signal]:
        """Check Google Trends interest for keywords related to a market.

        Args:
            keywords: Key terms from the market question.
            ctx: Trading context.
        """
        api_key = ctx.config.serp_api_key.get_secret_value()
        if not api_key:
            logger.debug("Trends: no SerpAPI key configured, skipping")
            return []

        # Google Trends supports up to 5 terms at once
        terms = keywords[:5]
        query = ",".join(terms)
        signals: list[Signal] = []

        try:
            async with httpx.AsyncClient(timeout=20.0) as http:
                resp = await http.get(
                    _SERP_TRENDS_URL,
                    params={
                        "api_key": api_key,
                        "engine": "google_trends",
                        "q": query,
                        "data_type": "TIMESERIES",
                        "date": "now 7-d",  # Last 7 days
                    },
                )
                resp.raise_for_status()
                data = resp.json()

                interest = data.get("interest_over_time", {})
                timeline = interest.get("timeline_data", [])

                if not timeline:
                    return []

                # Check if any keyword is surging (last value > 2x average)
                for keyword_idx, keyword in enumerate(terms):
                    values = []
                    for point in timeline:
                        point_values = point.get("values", [])
                        if keyword_idx < len(point_values):
                            val = point_values[keyword_idx].get("extracted_value", 0)
                            values.append(val)

                    if not values or len(values) < 3:
                        continue

                    recent = values[-1]
                    avg = sum(values[:-1]) / len(values[:-1]) if len(values) > 1 else 1
                    avg = max(avg, 1)  # Avoid division by zero

                    surge_ratio = recent / avg
                    is_surging = surge_ratio > 1.5

                    # Map surge ratio to relevance
                    relevance = min(1.0, surge_ratio / 5.0)

                    # Surging interest is bullish for "Will X happen?" markets
                    # (more attention → more likely to resolve YES)
                    sentiment = min(1.0, (surge_ratio - 1.0) * 0.5) if is_surging else 0.0

                    signals.append(
                        Signal(
                            source="trends",
                            title=f"Google Trends: '{keyword}' {'SURGING' if is_surging else 'stable'}",
                            body=(
                                f"Interest level: {recent}/100. "
                                f"7-day average: {avg:.0f}/100. "
                                f"Surge ratio: {surge_ratio:.1f}x"
                            ),
                            published_at=datetime.now(timezone.utc),
                            sentiment=round(sentiment, 3),
                            relevance=round(relevance, 3),
                            metadata={
                                "keyword": keyword,
                                "current_interest": recent,
                                "avg_interest": round(avg, 1),
                                "surge_ratio": round(surge_ratio, 2),
                                "is_surging": is_surging,
                            },
                        )
                    )

        except Exception as e:
            logger.warning(f"Trends check failed: {e}")

        logger.info(f"Trends: collected {len(signals)} signals for {terms}")
        return signals
