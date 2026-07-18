"""Fraud / Risk triage agent — summarize alerts, rank by severity."""

from __future__ import annotations

from typing import Any

from agents.state import AgentState
from tools.tool_registry import get_tool_registry

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


async def run_fraud_agent(state: AgentState) -> dict[str, Any]:
    if state.get("role") != "staff":
        return {
            "final_answer": (
                "Fraud/Risk Triage is staff-only. "
                "Customers should report suspected fraud via Dispute Intake."
            ),
            "draft_answer": "Staff only.",
            "grounded": True,
            "abstained": True,
            "trace": [{"step": "fraud_denied"}],
        }

    registry = get_tool_registry()
    alerts = registry.call("list_fraud_alerts", role="staff")
    alerts_sorted = sorted(alerts, key=lambda a: SEVERITY_ORDER.get(a["severity"], 9))

    lines = [
        f"**Fraud/Risk triage** — {len(alerts_sorted)} alert(s), ranked by severity:\n"
    ]
    for a in alerts_sorted:
        inds = ", ".join(a.get("indicators") or []) or "n/a"
        amt = f"${a['amount']:,.2f}" if a.get("amount") is not None else "n/a"
        lines.append(
            f"- **{a['severity'].upper()}** `{a['alert_id']}` · customer `{a['customer_id']}` · "
            f"txn `{a.get('txn_id')}` · amount {amt}\n"
            f"  Reason: {a['reason']}\n"
            f"  Indicators: {inds} · status: {a['status']}"
        )

    lines.append(
        "\n_Recommended next steps are advisory. Case disposition requires a human investigator._"
    )
    answer = "\n".join(lines)
    return {
        "tool_results": [{"tool": "list_fraud_alerts", "result": alerts_sorted}],
        "final_answer": answer,
        "draft_answer": answer,
        "grounded": True,
        "abstained": False,
        "require_hitl": False,
        "trace": [{"step": "fraud_triage", "n_alerts": len(alerts_sorted)}],
    }
