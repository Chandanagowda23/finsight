"""Role-aware tool registry — customer agents cannot call staff-only tools."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from tools.mock_core_banking_api import get_banking_api
from tools.schemas import DisputeDraft, EligibilityInput

ToolFn = Callable[..., Any]


STAFF_ONLY = {"list_fraud_alerts", "triage_alerts"}
CUSTOMER_OK = {
    "get_balance",
    "list_accounts",
    "list_transactions",
    "list_cards",
    "get_card",
    "draft_dispute",
    "freeze_card_request",
    "eligibility_precheck",
}


class ToolRegistry:
    def __init__(self) -> None:
        api = get_banking_api()
        self._tools: dict[str, ToolFn] = {
            "get_balance": lambda **kw: api.get_balance(**kw).model_dump(mode="json"),
            "list_accounts": lambda **kw: api.list_accounts(**kw),
            "list_transactions": lambda **kw: [
                t.model_dump(mode="json") for t in api.list_transactions(**kw)
            ],
            "list_cards": lambda **kw: [c.model_dump(mode="json") for c in api.list_cards(**kw)],
            "get_card": lambda **kw: api.get_card(**kw).model_dump(mode="json"),
            "list_fraud_alerts": lambda **kw: [
                a.model_dump(mode="json") for a in api.list_fraud_alerts(**kw)
            ],
            "draft_dispute": lambda **kw: api.draft_dispute(DisputeDraft(**kw)),
            "freeze_card_request": lambda **kw: api.freeze_card_request(**kw),
            "eligibility_precheck": lambda **kw: api.eligibility_precheck(
                EligibilityInput(**kw)
            ).model_dump(mode="json"),
        }

    def call(self, name: str, *, role: str, **kwargs: Any) -> Any:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        if role == "customer" and name in STAFF_ONLY:
            raise PermissionError(f"Tool '{name}' is staff-only")
        if role == "customer" and name not in CUSTOMER_OK:
            raise PermissionError(f"Tool '{name}' not permitted for customer role")
        return self._tools[name](**kwargs)

    def list_for_role(self, role: str) -> list[str]:
        if role == "staff":
            return sorted(self._tools.keys())
        return sorted(CUSTOMER_OK)


_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
