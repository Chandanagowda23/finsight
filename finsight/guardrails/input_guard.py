"""Input guardrails: PII redaction, prompt-injection filter, scope classifier."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from api.config import get_settings

POLICY_PATH = Path(__file__).parent / "policies" / "compliance_rules.yaml"

# Lightweight PII patterns (Presidio optional — always have regex fallback)
PII_PATTERNS = [
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("CREDIT_CARD", re.compile(r"\b(?:\d[ -]*?){13,19}\b")),
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")),
    ("PHONE", re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")),
]


@dataclass
class InputGuardResult:
    allowed: bool
    redacted_text: str
    original_text: str
    pii_found: list[str] = field(default_factory=list)
    block_reason: str | None = None
    scope: str = "in_scope"  # in_scope | out_of_scope | injection


@lru_cache
def _load_policy() -> dict[str, Any]:
    with open(POLICY_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def clear_policy_cache() -> None:
    _load_policy.cache_clear()


def _presidio_redact(text: str) -> tuple[str, list[str]]:
    try:
        from presidio_analyzer import AnalyzerEngine
        from presidio_anonymizer import AnonymizerEngine

        analyzer = AnalyzerEngine()
        anonymizer = AnonymizerEngine()
        results = analyzer.analyze(text=text, language="en")
        if not results:
            return text, []
        anonymized = anonymizer.anonymize(text=text, analyzer_results=results)
        types = sorted({r.entity_type for r in results})
        return anonymized.text, types
    except Exception:
        return text, []


def _regex_redact(text: str) -> tuple[str, list[str]]:
    found: list[str] = []
    out = text
    for label, pattern in PII_PATTERNS:
        if pattern.search(out):
            found.append(label)
            out = pattern.sub(f"<{label}>", out)
    return out, found


def redact_pii(text: str) -> tuple[str, list[str]]:
    if not get_settings().pii_redaction_enabled:
        return text, []
    redacted, found = _presidio_redact(text)
    # Always run regex as safety net
    redacted2, found2 = _regex_redact(redacted)
    return redacted2, sorted(set(found + found2))


def check_injection_and_scope(text: str) -> tuple[bool, str | None, str]:
    policy = _load_policy()
    lower = text.lower()
    for block in policy.get("topic_blocks", []):
        if re.search(block["pattern"], lower, flags=re.I):
            return False, block.get("message", "Request blocked by policy."), "injection"
    # Soft scope: banking-ish keywords OR greetings allowed through
    banking_signals = [
        "account",
        "balance",
        "fee",
        "card",
        "loan",
        "mortgage",
        "dispute",
        "transaction",
        "apr",
        "rate",
        "policy",
        "kyc",
        "aml",
        "fraud",
        "statement",
        "transfer",
        "savings",
        "checking",
        "eligib",
        "regulation",
        "compliance",
        "sop",
        "help",
        "hello",
        "hi ",
    ]
    if len(text) < 8:
        return True, None, "in_scope"
    if any(s in lower for s in banking_signals):
        return True, None, "in_scope"
    # Allow through — orchestrator may still abstain; don't over-block
    return True, None, "in_scope"


def run_input_guard(text: str) -> InputGuardResult:
    redacted, pii = redact_pii(text)
    allowed, reason, scope = check_injection_and_scope(redacted)
    return InputGuardResult(
        allowed=allowed,
        redacted_text=redacted,
        original_text=text,
        pii_found=pii,
        block_reason=reason,
        scope=scope,
    )
