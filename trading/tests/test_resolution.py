"""Tests for market resolution module."""

from __future__ import annotations

import pytest

from src.core.resolution import _determine_outcome


class TestDetermineOutcome:
    """Tests for outcome determination from resolved market prices."""

    def test_yes_outcome(self) -> None:
        assert _determine_outcome(["1.0", "0.0"]) == 1

    def test_no_outcome(self) -> None:
        assert _determine_outcome(["0.0", "1.0"]) == 0

    def test_yes_at_threshold(self) -> None:
        assert _determine_outcome(["0.95", "0.05"]) == 1

    def test_no_at_threshold(self) -> None:
        assert _determine_outcome(["0.05", "0.95"]) == 0

    def test_ambiguous_prices(self) -> None:
        assert _determine_outcome(["0.50", "0.50"]) is None

    def test_near_threshold(self) -> None:
        assert _determine_outcome(["0.94", "0.06"]) is None

    def test_empty_prices(self) -> None:
        assert _determine_outcome([]) is None

    def test_single_price(self) -> None:
        assert _determine_outcome(["1.0"]) is None

    def test_invalid_price_string(self) -> None:
        assert _determine_outcome(["abc", "xyz"]) is None

    def test_none_input(self) -> None:
        assert _determine_outcome(None) is None
