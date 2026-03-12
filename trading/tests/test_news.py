"""Tests for news monitoring module."""

from __future__ import annotations

import pytest

from src.core.news import NewsSentinel, NewsEvent
from datetime import datetime, timezone


class TestNewsSentinelMatchMarkets:
    """Tests for market-news matching logic."""

    def _event(self, title: str) -> NewsEvent:
        return NewsEvent(
            title=title,
            source="test",
            url="https://example.com",
            published_at=datetime.now(timezone.utc),
            relevance_score=0.5,
        )

    def test_matches_overlapping_keywords(self) -> None:
        sentinel = NewsSentinel()
        events = [self._event("Bitcoin price hits new record high")]
        questions = ["Will Bitcoin price reach a new high?"]
        matches = sentinel.match_markets(events, questions)
        assert len(matches) > 0

    def test_no_match_with_no_overlap(self) -> None:
        sentinel = NewsSentinel()
        events = [self._event("Weather forecast for tomorrow")]
        questions = ["Will Bitcoin reach $100k?"]
        matches = sentinel.match_markets(events, questions)
        assert len(matches) == 0

    def test_empty_events(self) -> None:
        sentinel = NewsSentinel()
        matches = sentinel.match_markets([], ["Will Bitcoin reach $100k?"])
        assert matches == {}

    def test_empty_questions(self) -> None:
        sentinel = NewsSentinel()
        events = [self._event("Bitcoin price hits record")]
        matches = sentinel.match_markets(events, [])
        assert matches == {}

    def test_case_insensitive_matching(self) -> None:
        sentinel = NewsSentinel()
        events = [self._event("BITCOIN PRICE SURGE")]
        questions = ["Will bitcoin price reach 100k?"]
        matches = sentinel.match_markets(events, questions)
        assert len(matches) > 0

    def test_multiple_events_multiple_questions(self) -> None:
        sentinel = NewsSentinel()
        events = [
            self._event("Bitcoin price hits record high"),
            self._event("Election results announced today"),
        ]
        questions = [
            "Will Bitcoin price hit a new high?",
            "Will the election results be contested?",
        ]
        matches = sentinel.match_markets(events, questions)
        # Each question should match its relevant event
        assert len(matches) >= 1
