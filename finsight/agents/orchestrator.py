"""LangGraph supervisor — intent classification + specialist routing + HITL."""

from __future__ import annotations

import json
import uuid
from typing import Any, Literal

import structlog
from langgraph.graph import END, StateGraph

from agents.account_agent import run_account_agent
from agents.compliance_agent import run_compliance_agent
from agents.dispute_agent import run_dispute_agent
from agents.eligibility_agent import run_eligibility_agent
from agents.fraud_agent import run_fraud_agent
from agents.knowledge_agent import run_knowledge_agent
from agents.service_copilot import run_service_copilot
from agents.state import AgentState
from api.audit import write_audit
from api.llm import get_llm
from guardrails.input_guard import run_input_guard

log = structlog.get_logger(__name__)

Route = Literal[
    "knowledge",
    "account",
    "dispute",
    "eligibility",
    "compliance",
    "fraud",
    "regulatory",
    "service_copilot",
]


CUSTOMER_ROUTES = {"knowledge", "account", "dispute", "eligibility"}
STAFF_ROUTES = CUSTOMER_ROUTES | {"compliance", "fraud", "regulatory", "service_copilot"}


async def input_guard_node(state: AgentState) -> dict[str, Any]:
    result = run_input_guard(state["user_message"])
    if not result.allowed:
        return {
            "redacted_message": result.redacted_text,
            "final_answer": result.block_reason or "Request blocked by input guardrails.",
            "draft_answer": result.block_reason or "Blocked.",
            "grounded": True,
            "abstained": True,
            "route": "blocked",
            "trace": [
                {
                    "step": "input_guard",
                    "allowed": False,
                    "pii": result.pii_found,
                    "scope": result.scope,
                }
            ],
        }
    return {
        "redacted_message": result.redacted_text,
        "trace": [
            {
                "step": "input_guard",
                "allowed": True,
                "pii": result.pii_found,
                "scope": result.scope,
            }
        ],
    }


async def classify_intent(state: AgentState) -> dict[str, Any]:
    if state.get("route") == "blocked":
        return {}
    llm = get_llm()
    role = state.get("role", "customer")
    allowed = sorted(STAFF_ROUTES if role == "staff" else CUSTOMER_ROUTES)
    raw = await llm.complete(
        [
            {
                "role": "system",
                "content": (
                    "Classify the banking user intent. "
                    f"Allowed intents: {allowed}. "
                    'Respond JSON: {"intent": str, "confidence": float, "rationale": str}.'
                ),
            },
            {"role": "user", "content": state.get("redacted_message") or state["user_message"]},
        ],
        json_mode=True,
        temperature=0.0,
    )
    try:
        data = json.loads(raw)
        intent = data.get("intent", "knowledge")
        conf = float(data.get("confidence", 0.5))
    except (json.JSONDecodeError, TypeError, ValueError):
        intent, conf = "knowledge", 0.5

    if intent == "regulatory":
        intent = "compliance"  # same corpus path with staff filter
    if intent not in allowed:
        intent = "knowledge"

    return {
        "intent": intent,
        "intent_confidence": conf,
        "route": intent,
        "trace": [{"step": "classify", "intent": intent, "confidence": conf}],
    }


def route_after_classify(state: AgentState) -> str:
    if state.get("route") == "blocked" or state.get("final_answer"):
        return "finalize"
    return state.get("route") or "knowledge"


async def finalize_node(state: AgentState) -> dict[str, Any]:
    answer = state.get("final_answer") or state.get("draft_answer") or (
        "I wasn't able to produce a verified answer. Please try rephrasing or contact support."
    )
    session_id = state.get("session_id") or str(uuid.uuid4())
    write_audit(
        actor=state.get("customer_id") or state.get("staff_id") or "anonymous",
        role=state.get("role", "customer"),
        event_type="agent_response",
        session_id=session_id,
        payload={
            "intent": state.get("intent"),
            "route": state.get("route"),
            "abstained": state.get("abstained", False),
            "grounded": state.get("grounded", False),
            "require_hitl": state.get("require_hitl", False),
            "hitl_id": state.get("hitl_id"),
            "citations": state.get("citations"),
            "compliance_flags": state.get("compliance_flags"),
            "answer_preview": answer[:500],
            "trace": state.get("trace"),
        },
    )
    return {
        "final_answer": answer,
        "session_id": session_id,
        "trace": [{"step": "finalize", "audited": True}],
    }


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("input_guard", input_guard_node)
    g.add_node("classify", classify_intent)
    g.add_node("knowledge", run_knowledge_agent)
    g.add_node("account", run_account_agent)
    g.add_node("dispute", run_dispute_agent)
    g.add_node("eligibility", run_eligibility_agent)
    g.add_node("compliance", run_compliance_agent)
    g.add_node("fraud", run_fraud_agent)
    g.add_node("service_copilot", run_service_copilot)
    g.add_node("finalize", finalize_node)

    g.set_entry_point("input_guard")
    g.add_edge("input_guard", "classify")
    g.add_conditional_edges(
        "classify",
        route_after_classify,
        {
            "knowledge": "knowledge",
            "account": "account",
            "dispute": "dispute",
            "eligibility": "eligibility",
            "compliance": "compliance",
            "fraud": "fraud",
            "service_copilot": "service_copilot",
            "finalize": "finalize",
        },
    )
    for node in (
        "knowledge",
        "account",
        "dispute",
        "eligibility",
        "compliance",
        "fraud",
        "service_copilot",
    ):
        g.add_edge(node, "finalize")
    g.add_edge("finalize", END)
    return g.compile()


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


async def run_orchestrator(
    *,
    message: str,
    role: str,
    customer_id: str | None = None,
    staff_id: str | None = None,
    session_id: str | None = None,
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    graph = get_graph()
    initial: AgentState = {
        "user_message": message,
        "role": role,  # type: ignore[typeddict-item]
        "customer_id": customer_id,
        "staff_id": staff_id,
        "session_id": session_id or str(uuid.uuid4()),
        "history": history or [],
        "tool_results": [],
        "trace": [],
    }
    final = await graph.ainvoke(initial)
    return {
        "session_id": final.get("session_id"),
        "answer": final.get("final_answer"),
        "intent": final.get("intent"),
        "route": final.get("route"),
        "abstained": final.get("abstained", False),
        "grounded": final.get("grounded", False),
        "confidence": final.get("confidence"),
        "citations": final.get("citations") or [],
        "retrieved_chunks": final.get("retrieved_chunks") or [],
        "require_hitl": final.get("require_hitl", False),
        "hitl_id": final.get("hitl_id"),
        "compliance_flags": final.get("compliance_flags") or [],
        "tool_results": final.get("tool_results") or [],
        "trace": final.get("trace") or [],
    }
