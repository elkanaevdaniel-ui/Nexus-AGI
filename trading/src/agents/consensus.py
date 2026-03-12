"""Multi-LLM consensus graph using LangGraph.

Fan-out: 3 LLMs run in parallel.
Fan-in: results feed into bull/bear debate, then synthesizer.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from src.agents.state import ConsensusState


async def call_claude_node(state: ConsensusState) -> dict:
    """Claude analyst node — returns estimate dict."""
    # In production, this calls the actual LLM via langchain
    # For build/test, returns a placeholder structure
    return {
        "claude_estimate": {
            "probability": 0.5,
            "confidence": "medium",
            "reasoning": "Claude analysis placeholder",
        },
        "messages": [{"role": "claude", "content": "Analysis complete"}],
    }


async def call_gemini_node(state: ConsensusState) -> dict:
    """Gemini analyst node."""
    return {
        "gemini_estimate": {
            "probability": 0.5,
            "confidence": "medium",
            "reasoning": "Gemini analysis placeholder",
        },
        "messages": [{"role": "gemini", "content": "Analysis complete"}],
    }


async def call_gpt_node(state: ConsensusState) -> dict:
    """GPT analyst node."""
    return {
        "gpt_estimate": {
            "probability": 0.5,
            "confidence": "medium",
            "reasoning": "GPT analysis placeholder",
        },
        "messages": [{"role": "gpt", "content": "Analysis complete"}],
    }


async def argue_bull_case(state: ConsensusState) -> dict:
    """Bull researcher — argues for higher probability."""
    estimates = []
    for key in ["claude_estimate", "gemini_estimate", "gpt_estimate"]:
        est = state.get(key)
        if est and isinstance(est, dict):
            estimates.append(est.get("probability", 0.5))

    avg = sum(estimates) / len(estimates) if estimates else 0.5

    return {
        "bull_case": f"Bull case: factors supporting higher probability (avg estimate: {avg:.3f})",
        "messages": [{"role": "bull", "content": "Bull case argued"}],
    }


async def argue_bear_case(state: ConsensusState) -> dict:
    """Bear researcher — argues for lower probability."""
    return {
        "bear_case": "Bear case: factors supporting lower probability",
        "messages": [{"role": "bear", "content": "Bear case argued"}],
    }


async def synthesize_consensus(state: ConsensusState) -> dict:
    """Synthesizer — produces final consensus from all inputs."""
    estimates = []
    for key in ["claude_estimate", "gemini_estimate", "gpt_estimate"]:
        est = state.get(key)
        if est and isinstance(est, dict):
            estimates.append(est.get("probability", 0.5))

    if estimates:
        consensus = sum(estimates) / len(estimates)
        spread = max(estimates) - min(estimates)
    else:
        consensus = 0.5
        spread = 0.0

    confidence = "high" if spread < 0.10 else "medium" if spread < 0.20 else "low"

    return {
        "consensus_probability": max(0.01, min(0.99, consensus)),
        "consensus_confidence": confidence,
        "messages": [
            {
                "role": "synthesizer",
                "content": f"Consensus: {consensus:.3f} ({confidence})",
            }
        ],
    }


def build_consensus_graph() -> Any:
    """Build the LangGraph consensus workflow.

    Returns the compiled graph, or None if langgraph is not available.
    """
    try:
        from langgraph.graph import END, START, StateGraph

        workflow = StateGraph(ConsensusState)

        workflow.add_node("claude_analyst", call_claude_node)
        workflow.add_node("gemini_analyst", call_gemini_node)
        workflow.add_node("gpt_analyst", call_gpt_node)
        workflow.add_node("bull_researcher", argue_bull_case)
        workflow.add_node("bear_researcher", argue_bear_case)
        workflow.add_node("synthesizer", synthesize_consensus)

        # Fan-out: all 3 analysts run from START
        workflow.add_edge(START, "claude_analyst")
        workflow.add_edge(START, "gemini_analyst")
        workflow.add_edge(START, "gpt_analyst")

        # Fan-in: all 3 -> bull -> bear -> synthesizer
        workflow.add_edge("claude_analyst", "bull_researcher")
        workflow.add_edge("gemini_analyst", "bull_researcher")
        workflow.add_edge("gpt_analyst", "bull_researcher")
        workflow.add_edge("bull_researcher", "bear_researcher")
        workflow.add_edge("bear_researcher", "synthesizer")
        workflow.add_edge("synthesizer", END)

        return workflow.compile()

    except ImportError:
        logger.info("langgraph not available — consensus graph disabled")
        return None
