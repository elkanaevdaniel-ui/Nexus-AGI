"""Bull/Bear adversarial debate subgraph for probability estimation."""

from __future__ import annotations

from loguru import logger


async def run_bull_bear_debate(
    question: str,
    context: str,
    initial_estimates: list[dict],
) -> dict:
    """Run a bull vs bear debate to stress-test probability estimates.

    Takes the initial estimates from multiple LLMs and generates
    adversarial arguments for both sides to refine the consensus.

    Returns:
        dict with "bull_case", "bear_case", and "adjusted_probability".
    """
    if not initial_estimates:
        return {
            "bull_case": "No data",
            "bear_case": "No data",
            "adjusted_probability": 0.5,
        }

    avg_prob = sum(e.get("probability", 0.5) for e in initial_estimates) / len(
        initial_estimates
    )

    # In production, this would call an LLM to generate adversarial arguments.
    # The LLM would be prompted to argue one side, then the other, and
    # the final adjusted probability would account for both perspectives.
    bull_factors = [
        e.get("reasoning", "")
        for e in initial_estimates
        if e.get("probability", 0.5) > avg_prob
    ]
    bear_factors = [
        e.get("reasoning", "")
        for e in initial_estimates
        if e.get("probability", 0.5) <= avg_prob
    ]

    return {
        "bull_case": " | ".join(bull_factors) or "No strong bull arguments",
        "bear_case": " | ".join(bear_factors) or "No strong bear arguments",
        "adjusted_probability": avg_prob,
    }
