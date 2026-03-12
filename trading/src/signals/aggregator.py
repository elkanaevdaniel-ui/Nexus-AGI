"""Signal aggregator — collects from all sources and builds market context."""

from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING

from loguru import logger

from src.signals.reddit import RedditCollector
from src.signals.search import SearchCollector
from src.signals.trends import TrendsCollector
from src.signals.twitter import TwitterCollector
from src.signals.types import MarketSignals, Signal

if TYPE_CHECKING:
    from src.context import TradingContext


class SignalAggregator:
    """Collects signals from all configured sources for a market question.

    Runs all collectors in parallel and merges results into a ranked,
    deduplicated signal set that gets injected into the LLM probability prompt.
    """

    def __init__(self) -> None:
        self._reddit = RedditCollector()
        self._twitter = TwitterCollector()
        self._search = SearchCollector()
        self._trends = TrendsCollector()

    async def gather(
        self,
        market_id: str,
        question: str,
        ctx: TradingContext,
    ) -> MarketSignals:
        """Gather signals from all sources for a market question.

        Runs collectors in parallel, deduplicates, ranks by relevance,
        and computes aggregate sentiment.
        """
        keywords = extract_keywords(question)

        # Run all collectors in parallel — each handles its own errors
        results = await asyncio.gather(
            self._search.collect(question, ctx),
            self._search.collect_news(question, ctx),
            self._reddit.collect(keywords, ctx),
            self._twitter.collect(keywords, ctx),
            self._trends.collect(keywords, ctx),
            return_exceptions=True,
        )

        all_signals: list[Signal] = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"Signal collector failed: {result}")
                continue
            all_signals.extend(result)

        # Deduplicate by URL
        seen_urls: set[str] = set()
        unique: list[Signal] = []
        for sig in all_signals:
            if sig.url and sig.url in seen_urls:
                continue
            if sig.url:
                seen_urls.add(sig.url)
            unique.append(sig)

        # Sort by relevance (highest first)
        unique.sort(key=lambda s: s.relevance, reverse=True)

        # Cap at top 30 to avoid context bloat
        top_signals = unique[:30]

        # Compute aggregate sentiment
        bullish = sum(1 for s in top_signals if s.sentiment > 0.1)
        bearish = sum(1 for s in top_signals if s.sentiment < -0.1)

        if top_signals:
            weighted_sum = sum(s.sentiment * s.relevance for s in top_signals)
            weight_total = sum(s.relevance for s in top_signals) or 1.0
            overall = weighted_sum / weight_total
        else:
            overall = 0.0

        market_signals = MarketSignals(
            market_id=market_id,
            question=question,
            signals=top_signals,
            overall_sentiment=round(overall, 3),
            signal_count=len(top_signals),
            bullish_count=bullish,
            bearish_count=bearish,
        )

        logger.info(
            f"Signals for '{question[:50]}': "
            f"{len(top_signals)} signals, sentiment={overall:.2f}, "
            f"bull={bullish} bear={bearish}"
        )

        return market_signals


def extract_keywords(question: str) -> list[str]:
    """Extract searchable keywords from a market question.

    Removes common stop words and question words to produce
    terms that work well in search APIs.
    """
    stop_words = {
        "will", "the", "a", "an", "be", "is", "are", "was", "were",
        "in", "on", "at", "to", "for", "of", "by", "from", "with",
        "and", "or", "not", "this", "that", "it", "its", "do", "does",
        "did", "has", "have", "had", "been", "being", "than", "more",
        "before", "after", "during", "between", "about", "above",
        "below", "into", "through", "over", "under", "again",
        "what", "which", "who", "whom", "when", "where", "why", "how",
        "if", "then", "there", "here", "all", "each", "every",
        "any", "both", "few", "other", "some", "such", "no",
    }

    # Remove punctuation except hyphens and apostrophes
    cleaned = re.sub(r"[^\w\s\-']", " ", question)
    words = cleaned.split()

    keywords = [
        w for w in words
        if w.lower() not in stop_words and len(w) > 2
    ]

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for kw in keywords:
        lower = kw.lower()
        if lower not in seen:
            seen.add(lower)
            unique.append(kw)

    return unique[:10]


def format_signals_for_prompt(market_signals: MarketSignals) -> str:
    """Format aggregated signals into a string for the LLM probability prompt.

    This is injected into the market context so the LLM can consider
    external evidence when estimating probability.
    """
    if not market_signals.signals:
        return "No external signals available."

    lines: list[str] = []
    lines.append(
        f"External signals ({market_signals.signal_count} sources, "
        f"sentiment={market_signals.overall_sentiment:+.2f}):"
    )

    # Group by source
    by_source: dict[str, list[Signal]] = {}
    for sig in market_signals.signals:
        by_source.setdefault(sig.source, []).append(sig)

    source_labels = {
        "search": "Google Search",
        "news": "News",
        "reddit": "Reddit",
        "twitter": "Twitter/X",
        "trends": "Google Trends",
    }

    for source, sigs in by_source.items():
        label = source_labels.get(source, source)
        lines.append(f"\n[{label}]")
        for sig in sigs[:5]:  # Top 5 per source
            title = sig.title[:150]
            if sig.body:
                lines.append(f"- {title}: {sig.body[:200]}")
            else:
                lines.append(f"- {title}")

    return "\n".join(lines)
