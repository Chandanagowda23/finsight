"""Compliance lookup agent — internal AML/KYC/SOP corpus with citations."""

from __future__ import annotations

from typing import Any

from agents.knowledge_agent import run_knowledge_agent
from agents.state import AgentState


async def run_compliance_agent(state: AgentState) -> dict[str, Any]:
    if state.get("role") != "staff":
        return {
            "final_answer": (
                "Compliance Lookup is available to authenticated staff only. "
                "Please sign in with a staff account."
            ),
            "draft_answer": "Staff only.",
            "grounded": True,
            "abstained": True,
            "trace": [{"step": "compliance_denied"}],
        }
    # Reuse knowledge pipeline but force staff access (already set by role)
    result = await run_knowledge_agent(state)
    # Prefix framing
    if result.get("final_answer") and not result.get("abstained"):
        result["final_answer"] = (
            "**Internal compliance guidance** (verify effective dates before acting):\n\n"
            + result["final_answer"]
        )
    result["trace"] = list(result.get("trace") or []) + [{"step": "compliance_agent"}]
    return result
