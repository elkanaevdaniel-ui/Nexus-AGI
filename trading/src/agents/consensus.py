"""Multi-LLM consensus graph using LangGraph.

Fan-out: 3 LLMs run in parallel via the unified router.
Fan-in: results feed into bull/bear debate, then synthesizer.

All LLM calls go through the unified LLM router service (services/llm-router)
to ensure consistent cost tracking, circuit breaking, and fallback chains.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx
from loguru import logger

from src.agents.state import ConsensusState

# Configuration
LLM_ROUTER_URL = os.getenv("LLM_ROUTER_URL", "http://localhost:5100")
LLM_TIMEOUT = int(os.getenv("LLM_CONSENSUS_TIMEOUT", "45"))


def _build_probability_prompt(state: ConsensusState) -> str:
    """Build the probability estimation prompt from market state."""
    market = state.get("market", {})
    question = market.get("question", "Unknown market question")
    description = market.get("description", "")
    current_price = market.get("price", "N/A")
    volume = market.get("volume", "N/A")
    end_date = market.get("end_date", "N/A")

    return (
        f"You are a prediction market analyst. Estimate the probability that the following "
        f"event resolves YES.\n\n"
        f"Question: {question}\n"
        f"Description: {description[:500]}\n"
        f"Current market price: {current_price}\n"
        f"24h volume: {volume}\n"
        f"End date: {end_date}\n\n"
        f"Respond ONLY with valid JSON:\n"
        f'{{"probability": <float 0.01-0.99>, "confidence": "<high|medium|low>", '
        f'"reasoning": "<2-3 sentence explanation>"}}'
    )


def _parse_llm_response(raw_text: str, provider_name: str) -> dict:
    """Parse LLM JSON response into estimate dict. Handles markdown fences."""
    try:
        cleaned = re.sub(r"\`\`\`(?:json)?\s*", "", raw_text).strip().rstrip("\`")
        data = json.loads(cleaned)
        prob = float(data.get("probability", 0.5))
        prob = max(0.01, min(0.99, prob))
        confidence = data.get("confidence", "medium")
        if confidence not in ("high", "medium", "low"):
            confidence = "medium"
        reasoning = data.get("reasoning", f"{provider_name} analysis")
        return {
            "probability": prob,
            "confidence": confidence,
            "reasoning": reasoning,
        }
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning("Failed to parse %s response: %s — raw: %s", provider_name, e, raw_text[:200])
        return {
            "probability": 0.5,
            "confidence": "low",
            "reasoning": f"{provider_name} response could not be parsed",
        }


async def _call_router(prompt: str, tier: str = "deep", preferred_provider: str | None = None) -> str:
    """Call the unified LLM router and return the response text."""
    payload: dict[str, Any] = {
        "messages": [{"role": "user", "content": prompt}],
        "tier": tier,
        "temperature": 0.2,
        "max_tokens": 300,
    }
    if preferred_provider:
        payload["preferred_provider"] = preferred_provider

    async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
        resp = await client.post(f"{LLM_ROUTER_URL}/v1/chat/completions", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()


async def call_claude_node(state: ConsensusState) -> dict:
    """Claude analyst node — calls Claude via the unified router."""
    prompt = _build_probability_prompt(state)
    try:
        raw = await _call_router(prompt, tier="deep", preferred_provider="anthropic")
        estimate = _parse_llm_response(raw, "Claude")
    except Exception as e:
        logger.error("Claude node failed: %s", e)
        estimate = {"probability": 0.5, "confidence": "low", "reasoning": f"Claude call failed: {e}"}

    return {
        "claude_estimate": estimate,
        "messages": [{"role": "claude", "content": f"Analysis: p={estimate['probability']:.3f}"}],
    }


async def call_gemini_node(state: ConsensusState) -> dict:
    """Gemini analyst node — calls Gemini via the unified router."""
    prompt = _build_probability_prompt(state)
    try:
        raw = await _call_router(prompt, tier="deep", preferred_provider="google")
        estimate = _parse_llm_response(raw, "Gemini")
    except Exception as e:
        logger.error("Gemini node failed: %s", e)
        estimate = {"probability": 0.5, "confidence": "low", "reasoning": f"Gemini call failed: {e}"}

    return {
        "gemini_estimate": estimate,
        "messages": [{"role": "gemini", "content": f"Analysis: p={estimate['probability']:.3f}"}],
    }


async def call_gpt_node(state: ConsensusState) -> dict:
    """GPT analyst node — calls GPT via the unified router."""
    prompt = _build_probability_prompt(state)
    try:
        raw = await _call_router(prompt, tier="balanced", preferred_provider="openrouter")
        estimate = _parse_llm_response(raw, "GPT")
    except Exception as e:
        logger.error("GPT node failed: %s", e)
        estimate = {"probability": 0.5, "confidence": "low", "reasoning": f"GPT call failed: {e}"}

    return {
        "gpt_estimate": estimate,
        "messages": [{"role": "gpt", "content": f"Analysis: p={estimate['probability']:.3f}"}],
    }



async def call_nemotron_node(state: ConsensusState) -> dict:
    """Nemotron analyst - agentic reasoning via NVIDIA NIM."""
    prompt = _build_probability_prompt(state)
    try:
        raw = await _call_router(prompt, tier="deep", preferred_provider="nvidia_nim")
        estimate = _parse_llm_response(raw, "Nemotron")
    except Exception as e:
        logger.error("Nemotron node failed: %s", e)
        estimate = {"probability": 0.5, "confidence": "low",
                    "reasoning": f"Nemotron call failed: {e}"}
    return {
        "nemotron_estimate": estimate,
        "messages": [{"role": "nemotron",
                      "content": "Analysis: p=%.3f" % estimate["probability"]}],
    }

async def argue_bull_case(state: ConsensusState) -> dict:
    """Bull researcher — argues for higher probability using LLM analysis."""
    estimates = []
    reasonings = []
    for key in ["claude_estimate", "gemini_estimate", "gpt_estimate", "nemotron_estimate"]:
        est = state.get(key)
        if est and isinstance(est, dict):
            estimates.append(est.get("probability", 0.5))
            reasonings.append(est.get("reasoning", ""))

    avg = sum(estimates) / len(estimates) if estimates else 0.5
    context = "; ".join(r for r in reasonings if r)

    try:
        prompt = (
            f"You are a bull-case analyst. Given these analyst estimates (avg: {avg:.3f}) "
            f"and their reasoning: {context[:500]}\n\n"
            f"Make the strongest case for why the probability should be HIGHER than {avg:.3f}. "
            f"Be specific and cite data. Keep it to 2-3 sentences."
        )
        raw = await _call_router(prompt, tier="fast")
        bull_case = raw[:500]
    except Exception as e:
        logger.warning("Bull case LLM failed: %s", e)
        bull_case = f"Bull case: factors supporting higher probability (avg estimate: {avg:.3f})"

    return {
        "bull_case": bull_case,
        "messages": [{"role": "bull", "content": "Bull case argued"}],
    }


async def argue_bear_case(state: ConsensusState) -> dict:
    """Bear researcher — argues for lower probability using LLM analysis."""
    estimates = []
    reasonings = []
    for key in ["claude_estimate", "gemini_estimate", "gpt_estimate", "nemotron_estimate"]:
        est = state.get(key)
        if est and isinstance(est, dict):
            estimates.append(est.get("probability", 0.5))
            reasonings.append(est.get("reasoning", ""))

    avg = sum(estimates) / len(estimates) if estimates else 0.5
    context = "; ".join(r for r in reasonings if r)

    try:
        prompt = (
            f"You are a bear-case analyst. Given these analyst estimates (avg: {avg:.3f}) "
            f"and their reasoning: {context[:500]}\n\n"
            f"Make the strongest case for why the probability should be LOWER than {avg:.3f}. "
            f"Be specific and cite risks/uncertainties. Keep it to 2-3 sentences."
        )
        raw = await _call_router(prompt, tier="fast")
        bear_case = raw[:500]
    except Exception as e:
        logger.warning("Bear case LLM failed: %s", e)
        bear_case = f"Bear case: factors supporting lower probability (avg: {avg:.3f})"

    return {
        "bear_case": bear_case,
        "messages": [{"role": "bear", "content": "Bear case argued"}],
    }


async def synthesize_consensus(state: ConsensusState) -> dict:
    """Synthesizer — produces final consensus from all inputs."""
    estimates = []
    for key in ["claude_estimate", "gemini_estimate", "gpt_estimate", "nemotron_estimate"]:
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
        workflow.add_node("nemotron_analyst", call_nemotron_node)
        workflow.add_node("bull_researcher", argue_bull_case)
        workflow.add_node("bear_researcher", argue_bear_case)
        workflow.add_node("synthesizer", synthesize_consensus)

        # Fan-out: all 3 analysts run from START
        workflow.add_edge(START, "claude_analyst")
        workflow.add_edge(START, "gemini_analyst")
        workflow.add_edge(START, "gpt_analyst")
        workflow.add_edge(START, "nemotron_analyst")

        # Fan-in: all 3 -> bull -> bear -> synthesizer
        workflow.add_edge("claude_analyst", "bull_researcher")
        workflow.add_edge("gemini_analyst", "bull_researcher")
        workflow.add_edge("gpt_analyst", "bull_researcher")
        workflow.add_edge("nemotron_analyst", "bull_researcher")
        workflow.add_edge("bull_researcher", "bear_researcher")
        workflow.add_edge("bear_researcher", "synthesizer")
        workflow.add_edge("synthesizer", END)

        graph = workflow.compile()
        logger.info("LangGraph consensus graph compiled successfully")
        return graph

    except ImportError:
        logger.warning("langgraph not installed — consensus graph unavailable")
        return None
