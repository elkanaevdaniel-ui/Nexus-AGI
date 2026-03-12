"""TypedDict state definitions for LangGraph consensus."""

from __future__ import annotations

from typing import Annotated, Optional, TypedDict

import operator


class ConsensusState(TypedDict):
    """State for the multi-LLM consensus graph."""

    question: str
    context: str
    market_price: float
    claude_estimate: Optional[dict]
    gemini_estimate: Optional[dict]
    gpt_estimate: Optional[dict]
    bull_case: str
    bear_case: str
    consensus_probability: float
    consensus_confidence: str
    messages: Annotated[list, operator.add]
