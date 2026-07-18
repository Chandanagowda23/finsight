"""Tool schemas for mock core-banking operations."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class CardStatus(StrEnum):
    ACTIVE = "active"
    FROZEN = "frozen"
    CLOSED = "closed"
    PENDING = "pending"


class AccountType(StrEnum):
    CHECKING = "checking"
    SAVINGS = "savings"
    CREDIT = "credit"


class BalanceResponse(BaseModel):
    account_id: str
    account_type: AccountType
    available: float
    ledger: float
    currency: str = "USD"
    as_of: str


class Transaction(BaseModel):
    txn_id: str
    account_id: str
    posted_date: date
    amount: float
    merchant: str
    category: str
    status: Literal["posted", "pending", "disputed"] = "posted"
    mcc: str | None = None


class CardInfo(BaseModel):
    card_id: str
    account_id: str
    last4: str
    status: CardStatus
    network: str
    expires: str


class FraudAlert(BaseModel):
    alert_id: str
    customer_id: str
    severity: Literal["low", "medium", "high", "critical"]
    reason: str
    txn_id: str | None = None
    amount: float | None = None
    indicators: list[str] = Field(default_factory=list)
    created_at: str
    status: Literal["open", "investigating", "cleared", "escalated"] = "open"


class DisputeDraft(BaseModel):
    customer_id: str
    account_id: str
    txn_id: str
    reason: str
    amount: float
    merchant: str
    narrative: str
    requested_action: Literal["chargeback", "provisional_credit", "investigation"] = "investigation"


class EligibilityInput(BaseModel):
    product: Literal["personal_loan", "credit_card", "mortgage_refi"]
    annual_income: float
    employment_years: float
    existing_relationship_months: int
    requested_amount: float | None = None


class EligibilityResult(BaseModel):
    product: str
    informational_estimate: str
    indicative_factors: list[str]
    disclaimer: str
    is_credit_decision: bool = False
