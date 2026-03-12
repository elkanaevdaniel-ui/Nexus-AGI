"""Seed the database with sample prediction market data for development.

Run with: python -m scripts.seed_markets
"""
from __future__ import annotations

import asyncio
import uuid

from src.data.database import create_engine, create_session_factory, create_tables
from src.data.repository import Repository
from src.config import StaticConfig


SAMPLE_MARKETS = [
    {
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "will-trump-win-2028")),
        "condition_id": "cond_trump_2028",
        "question": "Will Donald Trump win the 2028 Presidential Election?",
        "description": "Resolves YES if Trump wins the 2028 US presidential election.",
        "category": "Politics",
        "volume": 52_400_000.0,
        "liquidity": 8_200_000.0,
        "outcome_yes_token": "tok_yes_trump28",
        "outcome_no_token": "tok_no_trump28",
        "current_price_yes": 0.12,
        "current_price_no": 0.88,
        "active": True,
    },
    {
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "bitcoin-100k-2026")),
        "condition_id": "cond_btc_100k",
        "question": "Will Bitcoin reach $100,000 by end of 2026?",
        "description": "Resolves YES if BTC/USD reaches $100,000 at any point before Dec 31, 2026.",
        "category": "Crypto",
        "volume": 38_700_000.0,
        "liquidity": 5_100_000.0,
        "outcome_yes_token": "tok_yes_btc100k",
        "outcome_no_token": "tok_no_btc100k",
        "current_price_yes": 0.72,
        "current_price_no": 0.28,
        "active": True,
    },
    {
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "fed-rate-cut-march-2026")),
        "condition_id": "cond_fed_march26",
        "question": "Will the Federal Reserve cut rates in March 2026?",
        "description": "Resolves YES if the FOMC announces a rate cut at the March 2026 meeting.",
        "category": "Economics",
        "volume": 21_300_000.0,
        "liquidity": 4_800_000.0,
        "outcome_yes_token": "tok_yes_fed_mar",
        "outcome_no_token": "tok_no_fed_mar",
        "current_price_yes": 0.35,
        "current_price_no": 0.65,
        "active": True,
    },
    {
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "agi-by-2030")),
        "condition_id": "cond_agi_2030",
        "question": "Will AGI be achieved by 2030?",
        "description": "Resolves YES based on expert panel consensus that AGI has been achieved.",
        "category": "Technology",
        "volume": 15_600_000.0,
        "liquidity": 3_200_000.0,
        "outcome_yes_token": "tok_yes_agi30",
        "outcome_no_token": "tok_no_agi30",
        "current_price_yes": 0.18,
        "current_price_no": 0.82,
        "active": True,
    },
    {
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "spacex-mars-2028")),
        "condition_id": "cond_spacex_mars",
        "question": "Will SpaceX land a Starship on Mars by 2028?",
        "description": "Resolves YES if SpaceX successfully lands a Starship on Mars before Jan 1, 2029.",
        "category": "Science",
        "volume": 12_100_000.0,
        "liquidity": 2_800_000.0,
        "outcome_yes_token": "tok_yes_mars28",
        "outcome_no_token": "tok_no_mars28",
        "current_price_yes": 0.05,
        "current_price_no": 0.95,
        "active": True,
    },
    {
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "ethereum-10k-2026")),
        "condition_id": "cond_eth_10k",
        "question": "Will Ethereum reach $10,000 by end of 2026?",
        "description": "Resolves YES if ETH/USD reaches $10,000 before Dec 31, 2026.",
        "category": "Crypto",
        "volume": 18_900_000.0,
        "liquidity": 4_100_000.0,
        "outcome_yes_token": "tok_yes_eth10k",
        "outcome_no_token": "tok_no_eth10k",
        "current_price_yes": 0.22,
        "current_price_no": 0.78,
        "active": True,
    },
    {
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "us-recession-2026")),
        "condition_id": "cond_recession_26",
        "question": "Will the US enter a recession in 2026?",
        "description": "Resolves YES if NBER declares a US recession starting in 2026.",
        "category": "Economics",
        "volume": 25_400_000.0,
        "liquidity": 6_300_000.0,
        "outcome_yes_token": "tok_yes_recess26",
        "outcome_no_token": "tok_no_recess26",
        "current_price_yes": 0.28,
        "current_price_no": 0.72,
        "active": True,
    },
    {
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "ai-regulation-eu-2026")),
        "condition_id": "cond_ai_reg_eu",
        "question": "Will the EU AI Act enforcement begin in 2026?",
        "description": "Resolves YES if EU AI Act enforcement provisions take effect in 2026.",
        "category": "Regulation",
        "volume": 8_700_000.0,
        "liquidity": 1_900_000.0,
        "outcome_yes_token": "tok_yes_airegeu",
        "outcome_no_token": "tok_no_airegeu",
        "current_price_yes": 0.89,
        "current_price_no": 0.11,
        "active": True,
    },
    {
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "nvidia-stock-200-2026")),
        "condition_id": "cond_nvda_200",
        "question": "Will NVIDIA stock reach $200 by end of Q2 2026?",
        "description": "Resolves YES if NVDA stock price reaches $200 before July 1, 2026.",
        "category": "Stocks",
        "volume": 31_200_000.0,
        "liquidity": 7_400_000.0,
        "outcome_yes_token": "tok_yes_nvda200",
        "outcome_no_token": "tok_no_nvda200",
        "current_price_yes": 0.55,
        "current_price_no": 0.45,
        "active": True,
    },
    {
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "world-cup-2026-winner")),
        "condition_id": "cond_wc26_brazil",
        "question": "Will Brazil win the 2026 FIFA World Cup?",
        "description": "Resolves YES if Brazil wins the 2026 FIFA World Cup.",
        "category": "Sports",
        "volume": 44_800_000.0,
        "liquidity": 9_500_000.0,
        "outcome_yes_token": "tok_yes_wc_br",
        "outcome_no_token": "tok_no_wc_br",
        "current_price_yes": 0.14,
        "current_price_no": 0.86,
        "active": True,
    },
]


async def seed() -> None:
    """Seed the database with sample markets."""
    config = StaticConfig()
    engine = await create_engine(config.database_url)
    await create_tables(engine)
    session_factory = create_session_factory(engine)
    repo = Repository(session_factory)

    for market in SAMPLE_MARKETS:
        await repo.upsert_market(market)
        print(f"  Seeded: {market['question'][:60]}...")

    print(f"\nSeeded {len(SAMPLE_MARKETS)} markets successfully.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
