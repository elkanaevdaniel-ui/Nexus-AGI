"""Walk-forward backtesting framework with Monte Carlo risk-of-ruin analysis."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass(frozen=True)
class BacktestTrade:
    """A single trade in the backtest."""

    market_id: str
    entry_price: float
    exit_price: float
    size_usd: float
    side: str  # BUY or SELL
    fee: float
    pnl: float


@dataclass
class BacktestResult:
    """Results from a backtest run."""

    trades: list[BacktestTrade] = field(default_factory=list)
    total_pnl: float = 0.0
    win_rate: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    num_trades: int = 0

    def summary(self) -> dict:
        return {
            "total_pnl": round(self.total_pnl, 2),
            "win_rate": round(self.win_rate, 4),
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "max_drawdown": round(self.max_drawdown, 4),
            "num_trades": self.num_trades,
        }


def run_backtest(
    trades: list[BacktestTrade],
    initial_bankroll: float = 1000.0,
) -> BacktestResult:
    """Run a walk-forward backtest on historical trades."""
    if not trades:
        return BacktestResult()

    equity = initial_bankroll
    peak = equity
    max_dd = 0.0
    pnls: list[float] = []
    wins = 0

    for trade in trades:
        equity += trade.pnl
        pnls.append(trade.pnl)
        if trade.pnl > 0:
            wins += 1
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd

    total_pnl = equity - initial_bankroll
    win_rate = wins / len(trades) if trades else 0

    # Sharpe ratio (annualized, assuming 1 trade/day)
    if len(pnls) > 1:
        mean_return = np.mean(pnls)
        std_return = np.std(pnls)
        sharpe = (mean_return / std_return * np.sqrt(365)) if std_return > 0 else 0
    else:
        sharpe = 0.0

    return BacktestResult(
        trades=trades,
        total_pnl=total_pnl,
        win_rate=win_rate,
        sharpe_ratio=float(sharpe),
        max_drawdown=max_dd,
        num_trades=len(trades),
    )


def monte_carlo_risk_of_ruin(
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    bankroll: float = 1000.0,
    num_simulations: int = 10000,
    num_trades: int = 500,
    ruin_threshold: float = 0.5,
    seed: Optional[int] = None,
) -> dict:
    """Monte Carlo simulation for risk of ruin.

    Simulates many trading paths and calculates the probability
    of drawdown exceeding the ruin threshold.

    Returns:
        dict with risk_of_ruin, median_final_equity, percentiles.
    """
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    ruin_count = 0
    final_equities: list[float] = []

    for _ in range(num_simulations):
        equity = bankroll
        min_equity = equity

        for _ in range(num_trades):
            if random.random() < win_rate:
                equity += avg_win
            else:
                equity -= avg_loss

            if equity < min_equity:
                min_equity = equity

            # Check ruin
            if equity <= bankroll * (1 - ruin_threshold):
                ruin_count += 1
                break

        final_equities.append(equity)

    final_arr = np.array(final_equities)

    return {
        "risk_of_ruin": ruin_count / num_simulations,
        "median_final_equity": float(np.median(final_arr)),
        "mean_final_equity": float(np.mean(final_arr)),
        "p5_equity": float(np.percentile(final_arr, 5)),
        "p25_equity": float(np.percentile(final_arr, 25)),
        "p75_equity": float(np.percentile(final_arr, 75)),
        "p95_equity": float(np.percentile(final_arr, 95)),
        "num_simulations": num_simulations,
        "num_trades": num_trades,
    }


def paper_trade_script() -> None:
    """Entry point for paper trading simulation."""
    print("Paper trading script — use run.py with TRADING_MODE=paper instead")


if __name__ == "__main__":
    # Example: Run Monte Carlo
    result = monte_carlo_risk_of_ruin(
        win_rate=0.55,
        avg_win=20.0,
        avg_loss=15.0,
        bankroll=1000.0,
        num_simulations=10000,
        num_trades=500,
        seed=42,
    )
    print("Monte Carlo Risk of Ruin Analysis:")
    for k, v in result.items():
        if isinstance(v, float):
            print(f"  {k}: {v:.4f}")
        else:
            print(f"  {k}: {v}")
