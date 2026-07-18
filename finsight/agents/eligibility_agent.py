"""Eligibility pre-check — informational only, never a credit decision."""

from __future__ import annotations

import re
from typing import Any

from agents.state import AgentState
from tools.tool_registry import get_tool_registry


def _parse_eligibility(msg: str) -> dict[str, Any]:
    lower = msg.lower()
    product = "credit_card"
    if "mortgage" in lower or "refi" in lower:
        product = "mortgage_refi"
    elif "loan" in lower:
        product = "personal_loan"

    income_m = re.search(r"income[:\s]*\$?([\d,]+)", lower)
    years_m = re.search(r"(\d+(?:\.\d+)?)\s*years?\s*(of\s*)?(employ|work)", lower)
    rel_m = re.search(r"(\d+)\s*months?\s*(as\s*)?(customer|member|relationship)", lower)
    amt_m = re.search(r"(request|need|want)[ing]?\s*\$?([\d,]+)", lower)

    return {
        "product": product,
        "annual_income": float(income_m.group(1).replace(",", "")) if income_m else 55000.0,
        "employment_years": float(years_m.group(1)) if years_m else 2.0,
        "existing_relationship_months": int(rel_m.group(1)) if rel_m else 12,
        "requested_amount": float(amt_m.group(2).replace(",", "")) if amt_m else None,
    }


async def run_eligibility_agent(state: AgentState) -> dict[str, Any]:
    registry = get_tool_registry()
    role = state.get("role", "customer")
    msg = state.get("redacted_message") or state["user_message"]
    params = _parse_eligibility(msg)
    result = registry.call("eligibility_precheck", role=role, **params)

    factors = "\n".join(f"- {f}" for f in result["indicative_factors"])
    answer = (
        f"### Informational eligibility pre-check — {result['product'].replace('_', ' ')}\n\n"
        f"**Estimate:** {result['informational_estimate']}\n\n"
        f"**Indicative factors considered:**\n{factors}\n\n"
        f"> {result['disclaimer']}\n\n"
        "_Assumptions used when not provided: income $55,000 · employment 2 years · "
        "relationship 12 months. Share your figures for a refined informational estimate._"
    )
    return {
        "tool_results": [{"tool": "eligibility_precheck", "result": result}],
        "final_answer": answer,
        "draft_answer": answer,
        "grounded": True,
        "abstained": False,
        "require_hitl": False,
        "compliance_flags": ["informational_only"],
        "trace": [{"step": "eligibility_precheck", "product": params["product"]}],
    }
