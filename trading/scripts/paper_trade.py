"""Paper trading entry point with realistic fill simulation."""

from __future__ import annotations

import os
import sys

# Ensure paper mode
os.environ["TRADING_MODE"] = "paper"


def main() -> None:
    """Start the agent in paper trading mode."""
    print("Starting Polymarket Agent in PAPER TRADING mode...")
    print("All trades will be simulated with realistic fills.")
    print()

    # Import and run the main app
    from run import main as run_main

    run_main()


if __name__ == "__main__":
    main()
