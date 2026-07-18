"""Shared LangGraph state schema for FinSight agents."""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict


class Message(TypedDict):
    role: str
    content: str


def _merge_lists(a: list, b: list) -> list:
    return (a or []) + (b or [])


class AgentState(TypedDict, total=False):
    # Input
    session_id: str
    user_message: str
    redacted_message: str
    role: Literal["customer", "staff"]
    customer_id: str | None
    staff_id: str | None
    history: list[Message]

    # Routing
    intent: str
    intent_confidence: float
    route: str

    # Retrieval / tools
    retrieved_chunks: list[dict[str, Any]]
    tool_results: Annotated[list[dict[str, Any]], operator.add]
    citations: list[str]

    # Generation
    draft_answer: str
    final_answer: str
    abstained: bool
    grounded: bool
    confidence: float
    require_hitl: bool
    hitl_id: str | None
    compliance_flags: list[str]

    # Trace
    trace: Annotated[list[dict[str, Any]], _merge_lists]
    error: str | None
