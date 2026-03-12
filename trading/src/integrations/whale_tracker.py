"""On-chain whale wallet monitoring as a supplementary signal."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Optional

import httpx
from loguru import logger

if TYPE_CHECKING:
    from src.context import TradingContext


@dataclass(frozen=True)
class WhaleTransaction:
    """A large transaction from a tracked wallet."""

    wallet: str
    market_id: str
    side: str  # BUY or SELL
    size_usd: float
    price: float
    timestamp: datetime


@dataclass
class WhaleTracker:
    """Tracks smart money wallets on Polymarket for supplementary signals.

    Monitors known profitable wallets and flags when they take positions.
    """

    watched_wallets: list[str] = field(default_factory=list)
    _recent_transactions: list[WhaleTransaction] = field(default_factory=list)
    _max_history: int = 1000

    def add_wallet(self, address: str) -> None:
        """Add a wallet address to track."""
        if address not in self.watched_wallets:
            self.watched_wallets.append(address)
            logger.info(f"Now tracking whale wallet: {address[:10]}...")

    def remove_wallet(self, address: str) -> None:
        """Remove a wallet from tracking."""
        if address in self.watched_wallets:
            self.watched_wallets.remove(address)

    async def check_activity(
        self, ctx: TradingContext
    ) -> list[WhaleTransaction]:
        """Check for recent whale activity.

        In production, this queries Polygon blockchain or Polymarket's
        activity API. In sandbox, returns empty.
        """
        new_transactions: list[WhaleTransaction] = []

        # Would query Polymarket activity API or Polygon RPC
        # For now, returns empty (external APIs unavailable in sandbox)

        if new_transactions:
            self._recent_transactions.extend(new_transactions)
            # Trim history
            if len(self._recent_transactions) > self._max_history:
                self._recent_transactions = self._recent_transactions[
                    -self._max_history :
                ]

        return new_transactions

    def get_whale_signal(self, market_id: str) -> Optional[dict]:
        """Get the aggregate whale signal for a market.

        Returns dict with side bias and total volume, or None if no activity.
        """
        relevant = [
            t for t in self._recent_transactions if t.market_id == market_id
        ]

        if not relevant:
            return None

        buy_volume = sum(t.size_usd for t in relevant if t.side == "BUY")
        sell_volume = sum(t.size_usd for t in relevant if t.side == "SELL")
        net = buy_volume - sell_volume

        return {
            "market_id": market_id,
            "buy_volume": buy_volume,
            "sell_volume": sell_volume,
            "net_volume": net,
            "bias": "BUY" if net > 0 else "SELL",
            "transaction_count": len(relevant),
        }
