"""Service co-pilot — suggests grounded replies for live staff; staff stays in control."""

from __future__ import annotations

from typing import Any

from agents.knowledge_agent import run_knowledge_agent
from agents.state import AgentState


async def run_service_copilot(state: AgentState) -> dict[str, Any]:
    if state.get("role") != "staff":
        return {
            "final_answer": "Service Co-Pilot is available on the staff console only.",
            "draft_answer": "Staff only.",
            "grounded": True,
            "abstained": True,
            "trace": [{"step": "copilot_denied"}],
        }

    # Treat user message as the customer utterance to respond to
    result = await run_knowledge_agent(state)
    suggestion = result.get("final_answer", "")
    framed = (
        "### Suggested reply for the customer\n"
        "_You stay in control — edit or discard before sending._\n\n"
        f"{suggestion}\n\n"
        "---\n"
        "Citations used: "
        + (", ".join(f"`{c}`" for c in (result.get("citations") or [])) or "_none_")
    )
    result["final_answer"] = framed
    result["draft_answer"] = suggestion
    result["trace"] = list(result.get("trace") or []) + [{"step": "service_copilot"}]
    return result
