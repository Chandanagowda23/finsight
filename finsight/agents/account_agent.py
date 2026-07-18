"""Account agent — balance, transactions, card status via mock core-banking tools."""

from __future__ import annotations

import re
from typing import Any

from agents.state import AgentState
from tools.tool_registry import get_tool_registry


async def run_account_agent(state: AgentState) -> dict[str, Any]:
    registry = get_tool_registry()
    role = state.get("role", "customer")
    customer_id = state.get("customer_id") or "CUST-1001"
    msg = (state.get("redacted_message") or state["user_message"]).lower()
    results: list[dict[str, Any]] = []
    lines: list[str] = []

    try:
        accounts = registry.call("list_accounts", role=role, customer_id=customer_id)
        results.append({"tool": "list_accounts", "result": accounts})

        if "card" in msg:
            cards = registry.call("list_cards", role=role, customer_id=customer_id)
            results.append({"tool": "list_cards", "result": cards})
            if not cards:
                lines.append("No cards found on your profile.")
            for c in cards:
                lines.append(
                    f"Card ending {c['last4']} ({c['network']}): status **{c['status']}**, "
                    f"expires {c['expires']}."
                )
            if "freeze" in msg or "block" in msg:
                card_id = cards[0]["card_id"] if cards else None
                if card_id:
                    freeze = registry.call(
                        "freeze_card_request",
                        role=role,
                        card_id=card_id,
                        customer_id=customer_id,
                    )
                    results.append({"tool": "freeze_card_request", "result": freeze})
                    lines.append(
                        f"{freeze['message']} Reply 'confirm freeze {card_id}' after reviewing — "
                        "a human/confirmation step is required; nothing has been executed."
                    )
                    return {
                        "tool_results": results,
                        "final_answer": "\n".join(lines),
                        "draft_answer": "\n".join(lines),
                        "grounded": True,
                        "abstained": False,
                        "require_hitl": True,
                        "trace": [{"step": "account_freeze_pending"}],
                    }

        # Balance
        if "balance" in msg or "how much" in msg or not any(
            k in msg for k in ("transaction", "history", "statement", "card")
        ):
            for acct in accounts:
                bal = registry.call(
                    "get_balance", role=role, account_id=acct, customer_id=customer_id
                )
                results.append({"tool": "get_balance", "result": bal})
                lines.append(
                    f"{bal['account_type'].title()} `{acct}`: "
                    f"available ${bal['available']:,.2f} "
                    f"(ledger ${bal['ledger']:,.2f}) as of {bal['as_of']}."
                )

        if "transaction" in msg or "history" in msg or "statement" in msg:
            # Prefer checking account if present
            target = next((a for a in accounts if "CHK" in a), accounts[0])
            m = re.search(r"ACC-[A-Z]+-\d+", state.get("user_message", ""))
            if m:
                target = m.group(0)
            txns = registry.call(
                "list_transactions",
                role=role,
                account_id=target,
                customer_id=customer_id,
                limit=10,
            )
            results.append({"tool": "list_transactions", "result": txns})
            lines.append(f"Recent transactions for `{target}`:")
            for t in txns:
                lines.append(
                    f"- {t['posted_date']}: {t['merchant']} "
                    f"${t['amount']:,.2f} ({t['status']}) [{t['txn_id']}]"
                )

        if not lines:
            lines.append(
                f"Your accounts: {', '.join(accounts)}. "
                "Ask about balance, transactions, or card status."
            )

        answer = "\n".join(lines)
        return {
            "tool_results": results,
            "final_answer": answer,
            "draft_answer": answer,
            "grounded": True,
            "abstained": False,
            "require_hitl": False,
            "citations": [],
            "trace": [{"step": "account_agent", "tools": [r["tool"] for r in results]}],
        }
    except (KeyError, PermissionError) as e:
        msg_out = f"I couldn't complete that account lookup: {e}"
        return {
            "tool_results": results,
            "final_answer": msg_out,
            "draft_answer": msg_out,
            "grounded": True,
            "error": str(e),
            "trace": [{"step": "account_agent_error", "error": str(e)}],
        }
