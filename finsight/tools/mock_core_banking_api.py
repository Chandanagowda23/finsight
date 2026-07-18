"""Realistic mock core-banking API — same shape a real adapter would implement."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from tools.schemas import (
    AccountType,
    BalanceResponse,
    CardInfo,
    CardStatus,
    DisputeDraft,
    EligibilityInput,
    EligibilityResult,
    FraudAlert,
    Transaction,
)

# Synthetic customers — no real PII
CUSTOMERS: dict[str, dict[str, Any]] = {
    "CUST-1001": {
        "name": "Alex Rivera",
        "email": "alex.rivera@example.com",
        "accounts": ["ACC-CHK-1001", "ACC-SAV-1001", "ACC-CRD-1001"],
    },
    "CUST-1002": {
        "name": "Jordan Lee",
        "email": "jordan.lee@example.com",
        "accounts": ["ACC-CHK-1002", "ACC-CRD-1002"],
    },
    "CUST-1003": {
        "name": "Sam Patel",
        "email": "sam.patel@example.com",
        "accounts": ["ACC-CHK-1003", "ACC-SAV-1003"],
    },
}

ACCOUNTS: dict[str, dict[str, Any]] = {
    "ACC-CHK-1001": {
        "customer_id": "CUST-1001",
        "type": AccountType.CHECKING,
        "available": 4287.55,
        "ledger": 4312.55,
    },
    "ACC-SAV-1001": {
        "customer_id": "CUST-1001",
        "type": AccountType.SAVINGS,
        "available": 15240.00,
        "ledger": 15240.00,
    },
    "ACC-CRD-1001": {
        "customer_id": "CUST-1001",
        "type": AccountType.CREDIT,
        "available": 3200.00,
        "ledger": -1800.00,
        "credit_limit": 5000.00,
    },
    "ACC-CHK-1002": {
        "customer_id": "CUST-1002",
        "type": AccountType.CHECKING,
        "available": 912.33,
        "ledger": 912.33,
    },
    "ACC-CRD-1002": {
        "customer_id": "CUST-1002",
        "type": AccountType.CREDIT,
        "available": 1500.00,
        "ledger": -450.00,
        "credit_limit": 2000.00,
    },
    "ACC-CHK-1003": {
        "customer_id": "CUST-1003",
        "type": AccountType.CHECKING,
        "available": 22010.00,
        "ledger": 22010.00,
    },
    "ACC-SAV-1003": {
        "customer_id": "CUST-1003",
        "type": AccountType.SAVINGS,
        "available": 50000.00,
        "ledger": 50000.00,
    },
}

_TODAY = date.today()

TRANSACTIONS: list[Transaction] = [
    Transaction(
        txn_id="TXN-9001",
        account_id="ACC-CHK-1001",
        posted_date=_TODAY - timedelta(days=1),
        amount=-48.20,
        merchant="Greenleaf Market",
        category="groceries",
    ),
    Transaction(
        txn_id="TXN-9002",
        account_id="ACC-CHK-1001",
        posted_date=_TODAY - timedelta(days=2),
        amount=-120.00,
        merchant="City Transit",
        category="transport",
    ),
    Transaction(
        txn_id="TXN-9003",
        account_id="ACC-CRD-1001",
        posted_date=_TODAY - timedelta(days=3),
        amount=-899.00,
        merchant="ElectroMart Online",
        category="electronics",
        status="posted",
        mcc="5732",
    ),
    Transaction(
        txn_id="TXN-9004",
        account_id="ACC-CRD-1001",
        posted_date=_TODAY - timedelta(days=4),
        amount=-12.99,
        merchant="StreamFlix",
        category="subscriptions",
    ),
    Transaction(
        txn_id="TXN-9005",
        account_id="ACC-CHK-1001",
        posted_date=_TODAY - timedelta(days=5),
        amount=2500.00,
        merchant="ACME Corp Payroll",
        category="income",
    ),
    Transaction(
        txn_id="TXN-9006",
        account_id="ACC-CHK-1002",
        posted_date=_TODAY - timedelta(days=1),
        amount=-75.00,
        merchant="Unknown Wire OUT",
        category="transfer",
        status="posted",
    ),
    Transaction(
        txn_id="TXN-9007",
        account_id="ACC-CRD-1002",
        posted_date=_TODAY,
        amount=-450.00,
        merchant="Overseas Gadgets Ltd",
        category="electronics",
        status="pending",
        mcc="5999",
    ),
]

CARDS: dict[str, CardInfo] = {
    "CARD-1001": CardInfo(
        card_id="CARD-1001",
        account_id="ACC-CRD-1001",
        last4="4412",
        status=CardStatus.ACTIVE,
        network="Visa",
        expires="09/28",
    ),
    "CARD-1002": CardInfo(
        card_id="CARD-1002",
        account_id="ACC-CRD-1002",
        last4="7781",
        status=CardStatus.ACTIVE,
        network="Mastercard",
        expires="01/27",
    ),
}

FRAUD_ALERTS: list[FraudAlert] = [
    FraudAlert(
        alert_id="ALERT-501",
        customer_id="CUST-1002",
        severity="high",
        reason="Unusual overseas merchant + velocity spike",
        txn_id="TXN-9007",
        amount=450.00,
        indicators=["geo_anomaly", "velocity_1h", "new_merchant"],
        created_at=(_TODAY.isoformat() + "T10:00:00Z"),
        status="open",
    ),
    FraudAlert(
        alert_id="ALERT-502",
        customer_id="CUST-1001",
        severity="medium",
        reason="Large electronics purchase atypical for profile",
        txn_id="TXN-9003",
        amount=899.00,
        indicators=["amount_outlier", "mcc_rare"],
        created_at=(_TODAY - timedelta(days=3)).isoformat() + "T14:00:00Z",
        status="investigating",
    ),
    FraudAlert(
        alert_id="ALERT-503",
        customer_id="CUST-1002",
        severity="critical",
        reason="Outbound wire to new beneficiary",
        txn_id="TXN-9006",
        amount=75.00,
        indicators=["new_beneficiary", "wire_out"],
        created_at=(_TODAY - timedelta(days=1)).isoformat() + "T09:00:00Z",
        status="open",
    ),
]


class MockCoreBankingAPI:
    """Interface-shaped mock. Swap with a real adapter behind the same methods."""

    def get_balance(self, account_id: str, customer_id: str | None = None) -> BalanceResponse:
        acct = ACCOUNTS.get(account_id)
        if not acct:
            raise KeyError(f"Unknown account {account_id}")
        if customer_id and acct["customer_id"] != customer_id:
            raise PermissionError("Account does not belong to customer")
        return BalanceResponse(
            account_id=account_id,
            account_type=acct["type"],
            available=acct["available"],
            ledger=acct["ledger"],
            as_of=date.today().isoformat(),
        )

    def list_accounts(self, customer_id: str) -> list[str]:
        cust = CUSTOMERS.get(customer_id)
        if not cust:
            raise KeyError(f"Unknown customer {customer_id}")
        return list(cust["accounts"])

    def list_transactions(
        self,
        account_id: str,
        *,
        customer_id: str | None = None,
        limit: int = 20,
    ) -> list[Transaction]:
        acct = ACCOUNTS.get(account_id)
        if not acct:
            raise KeyError(f"Unknown account {account_id}")
        if customer_id and acct["customer_id"] != customer_id:
            raise PermissionError("Account does not belong to customer")
        txns = [t for t in TRANSACTIONS if t.account_id == account_id]
        txns.sort(key=lambda t: t.posted_date, reverse=True)
        return txns[:limit]

    def get_card(self, card_id: str, customer_id: str | None = None) -> CardInfo:
        card = CARDS.get(card_id)
        if not card:
            raise KeyError(f"Unknown card {card_id}")
        acct = ACCOUNTS[card.account_id]
        if customer_id and acct["customer_id"] != customer_id:
            raise PermissionError("Card does not belong to customer")
        return card

    def list_cards(self, customer_id: str) -> list[CardInfo]:
        accounts = set(self.list_accounts(customer_id))
        return [c for c in CARDS.values() if c.account_id in accounts]

    def list_fraud_alerts(
        self,
        *,
        customer_id: str | None = None,
        min_severity: str | None = None,
    ) -> list[FraudAlert]:
        order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        alerts = FRAUD_ALERTS
        if customer_id:
            alerts = [a for a in alerts if a.customer_id == customer_id]
        if min_severity:
            alerts = [a for a in alerts if order[a.severity] >= order[min_severity]]
        return sorted(alerts, key=lambda a: order[a.severity], reverse=True)

    def draft_dispute(self, draft: DisputeDraft) -> dict[str, Any]:
        """Prepare only — never files. Human approval required."""
        return {
            "status": "draft_pending_human_approval",
            "draft": draft.model_dump(mode="json"),
            "message": "Dispute ticket drafted. A human reviewer must approve before filing.",
        }

    def freeze_card_request(self, card_id: str, customer_id: str) -> dict[str, Any]:
        card = self.get_card(card_id, customer_id)
        return {
            "status": "pending_confirmation",
            "card_id": card.card_id,
            "last4": card.last4,
            "message": "Card freeze prepared. Explicit customer confirmation required to execute.",
            "irreversible": True,
        }

    def eligibility_precheck(self, data: EligibilityInput) -> EligibilityResult:
        factors = []
        score = 0
        if data.annual_income >= 40000:
            factors.append("Income above informational threshold")
            score += 1
        else:
            factors.append("Income below typical informational threshold")
        if data.employment_years >= 1:
            factors.append("Employment tenure ≥ 1 year")
            score += 1
        if data.existing_relationship_months >= 6:
            factors.append("Existing bank relationship ≥ 6 months")
            score += 1
        if data.requested_amount and data.annual_income:
            if data.requested_amount < 0.4 * data.annual_income:
                factors.append("Requested amount within common debt-to-income heuristic")
                score += 1

        estimate = (
            "May meet common informational criteria for further review"
            if score >= 2
            else "May not meet common informational criteria — a banker review is required"
        )
        return EligibilityResult(
            product=data.product,
            informational_estimate=estimate,
            indicative_factors=factors,
            disclaimer=(
                "This is an informational pre-check only and is NOT a credit decision, "
                "offer, or commitment to lend. Formal underwriting is required."
            ),
            is_credit_decision=False,
        )


_api: MockCoreBankingAPI | None = None


def get_banking_api() -> MockCoreBankingAPI:
    global _api
    if _api is None:
        _api = MockCoreBankingAPI()
    return _api
