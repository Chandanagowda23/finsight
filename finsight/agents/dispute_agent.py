"""Dispute intake agent — interviews, drafts ticket, always requires human approval."""

from __future__ import annotations

import re
from typing import Any

from agents.state import AgentState
from api.audit import enqueue_hitl
from tools.tool_registry import get_tool_registry


async def run_dispute_agent(state: AgentState) -> dict[str, Any]:
    registry = get_tool_registry()
    role = state.get("role", "customer")
    customer_id = state.get("customer_id") or "CUST-1001"
    msg = state.get("redacted_message") or state["user_message"]

    # Try to extract structured fields from free text
    txn_match = re.search(r"TXN-\d+", msg, re.I)
    amount_match = re.search(r"\$?\s*(\d+(?:\.\d{2})?)", msg)
    reason = msg.strip()

    # Gather a candidate transaction if possible
    accounts = registry.call("list_accounts", role=role, customer_id=customer_id)
    txn_id = txn_match.group(0).upper() if txn_match else None
    account_id = accounts[0] if accounts else "ACC-CHK-1001"
    merchant = "Unknown merchant"
    amount = float(amount_match.group(1)) if amount_match else 0.0

    if not txn_id:
        # Pick most recent non-income txn as suggestion
        for acct in accounts:
            txns = registry.call(
                "list_transactions",
                role=role,
                account_id=acct,
                customer_id=customer_id,
                limit=5,
            )
            for t in txns:
                if t["amount"] < 0:
                    txn_id = t["txn_id"]
                    account_id = acct
                    merchant = t["merchant"]
                    amount = abs(t["amount"])
                    break
            if txn_id:
                break

    if not txn_id:
        answer = (
            "I can help draft a dispute for human review. Please share:\n"
            "1) Transaction ID (e.g. TXN-9003)\n"
            "2) Amount and merchant\n"
            "3) Reason (unauthorized, incorrect amount, goods not received, etc.)\n\n"
            "**Nothing will be filed until a specialist approves the draft.**"
        )
        return {
            "final_answer": answer,
            "draft_answer": answer,
            "grounded": True,
            "require_hitl": False,
            "trace": [{"step": "dispute_needs_info"}],
        }

    draft_payload = {
        "customer_id": customer_id,
        "account_id": account_id,
        "txn_id": txn_id,
        "reason": reason[:500],
        "amount": amount,
        "merchant": merchant,
        "narrative": f"Customer-reported dispute via FinSight: {reason[:800]}",
        "requested_action": "investigation",
    }
    drafted = registry.call("draft_dispute", role=role, **draft_payload)
    hitl_id = enqueue_hitl(
        kind="dispute_filing",
        actor=customer_id,
        summary=f"Dispute draft for {txn_id} · ${amount:.2f} · {merchant}",
        payload=drafted,
    )

    answer = (
        f"**Dispute draft prepared** (pending human approval)\n\n"
        f"- Ticket queue ID: `{hitl_id}`\n"
        f"- Transaction: `{txn_id}`\n"
        f"- Account: `{account_id}`\n"
        f"- Merchant: {merchant}\n"
        f"- Amount: ${amount:,.2f}\n"
        f"- Status: `{drafted['status']}`\n\n"
        f"{drafted['message']}\n\n"
        "A specialist will review before anything is filed with the network."
    )
    return {
        "tool_results": [{"tool": "draft_dispute", "result": drafted}],
        "final_answer": answer,
        "draft_answer": answer,
        "grounded": True,
        "require_hitl": True,
        "hitl_id": hitl_id,
        "trace": [{"step": "dispute_drafted", "hitl_id": hitl_id}],
    }
