"""Tests for calibration tracking — Brier score and ECE."""

from __future__ import annotations

import pytest

from src.core.probability import CalibrationTracker


class TestCalibration:
    """Test Brier score computation and tracking."""

    @pytest.mark.asyncio
    async def test_perfect_prediction_brier(self, repo) -> None:
        """Perfect prediction should have Brier score near 0."""
        tracker = CalibrationTracker(repo)

        await repo.save_probability_estimate({
            "market_id": "perfect",
            "model": "claude",
            "probability": 0.99,
            "confidence": "high",
            "reasoning": "certain",
            "market_price_at_estimate": 0.50,
        })

        scores = await tracker.record_resolution("perfect", 1)
        assert len(scores) == 1
        assert scores[0] < 0.01  # (0.99 - 1)^2 = 0.0001

    @pytest.mark.asyncio
    async def test_worst_prediction_brier(self, repo) -> None:
        """Worst prediction should have Brier score near 1."""
        tracker = CalibrationTracker(repo)

        await repo.save_probability_estimate({
            "market_id": "worst",
            "model": "claude",
            "probability": 0.01,
            "confidence": "high",
            "reasoning": "wrong",
            "market_price_at_estimate": 0.50,
        })

        scores = await tracker.record_resolution("worst", 1)
        assert len(scores) == 1
        assert scores[0] > 0.95  # (0.01 - 1)^2 = 0.9801

    @pytest.mark.asyncio
    async def test_naive_baseline_brier(self, repo) -> None:
        """0.50 prediction should have Brier score of 0.25."""
        tracker = CalibrationTracker(repo)

        await repo.save_probability_estimate({
            "market_id": "naive",
            "model": "claude",
            "probability": 0.50,
            "confidence": "low",
            "reasoning": "coin flip",
            "market_price_at_estimate": 0.50,
        })

        scores = await tracker.record_resolution("naive", 1)
        assert abs(scores[0] - 0.25) < 0.001  # (0.5 - 1)^2 = 0.25

    @pytest.mark.asyncio
    async def test_rolling_brier_with_data(self, repo) -> None:
        tracker = CalibrationTracker(repo)

        # Add two estimates with known scores
        for market_id, prob, outcome in [("a", 0.8, 1), ("b", 0.3, 0)]:
            await repo.save_probability_estimate({
                "market_id": market_id,
                "model": "claude",
                "probability": prob,
                "confidence": "medium",
                "reasoning": "test",
                "market_price_at_estimate": 0.5,
            })
            await tracker.record_resolution(market_id, outcome)

        rolling = await tracker.get_rolling_brier(100)
        # (0.8-1)^2 = 0.04, (0.3-0)^2 = 0.09, avg = 0.065
        assert abs(rolling - 0.065) < 0.01
