"""Historical data collection pipeline for backtesting."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx


async def collect_markets(
    output_dir: str = "data/markets",
    limit: int = 1000,
) -> int:
    """Collect market data from Gamma API for backtesting.

    Saves JSON files of market data grouped by date.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(timeout=30.0) as client:
        offset = 0
        batch_size = 100
        all_markets: list[dict] = []

        while offset < limit:
            response = await client.get(
                "https://gamma-api.polymarket.com/markets",
                params={
                    "limit": batch_size,
                    "offset": offset,
                    "order": "volume",
                    "ascending": "false",
                },
            )
            if response.status_code != 200:
                break

            data = response.json()
            if not data:
                break

            all_markets.extend(data)
            offset += batch_size

        # Save to file
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filepath = Path(output_dir) / f"markets_{timestamp}.json"
        filepath.write_text(json.dumps(all_markets, indent=2))

        print(f"Collected {len(all_markets)} markets -> {filepath}")
        return len(all_markets)


if __name__ == "__main__":
    asyncio.run(collect_markets())
