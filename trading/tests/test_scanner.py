"""Tests for market scanner module."""

from __future__ import annotations

import pytest

from src.core.scanner import _has_valid_tokens, _not_expired, rank_markets
from src.data.schemas import GammaMarket


def _market(**kwargs) -> GammaMarket:
    defaults = {
        "id": "test",
        "condition_id": "cond1",
        "question": "Test?",
        "volume": 50000.0,
        "liquidity": 10000.0,
        "clob_token_ids": ["tok1", "tok2"],
        "outcome_prices": ["0.50", "0.50"],
    }
    defaults.update(kwargs)
    return GammaMarket(**defaults)


class TestHasValidTokens:
    def test_valid_with_two_tokens(self) -> None:
        assert _has_valid_tokens(_market()) is True

    def test_invalid_with_one_token(self) -> None:
        assert _has_valid_tokens(_market(clob_token_ids=["tok1"])) is False

    def test_invalid_with_empty_tokens(self) -> None:
        assert _has_valid_tokens(_market(clob_token_ids=[])) is False


class TestNotExpired:
    def test_no_end_date_is_valid(self) -> None:
        assert _not_expired(_market(end_date_iso=None)) is True

    def test_future_date_is_valid(self) -> None:
        assert _not_expired(_market(end_date_iso="2099-12-31T00:00:00Z")) is True

    def test_past_date_is_expired(self) -> None:
        assert _not_expired(_market(end_date_iso="2020-01-01T00:00:00Z")) is False

    def test_malformed_date_is_valid(self) -> None:
        assert _not_expired(_market(end_date_iso="not-a-date")) is True


class TestRankMarkets:
    def test_ranks_by_composite_score(self) -> None:
        m1 = _market(id="low", volume=1000, liquidity=1000)
        m2 = _market(id="high", volume=100000, liquidity=50000)
        m3 = _market(id="mid", volume=50000, liquidity=20000)
        ranked = rank_markets([m1, m2, m3])
        assert ranked[0].id == "high"
        assert ranked[-1].id == "low"

    def test_empty_list(self) -> None:
        assert rank_markets([]) == []

    def test_single_market(self) -> None:
        m = _market()
        assert rank_markets([m]) == [m]
