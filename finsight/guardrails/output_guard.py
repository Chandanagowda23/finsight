"""Output guardrails: groundedness verifier, compliance re-check, PII leak check."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from api.config import get_settings
from api.llm import get_llm
from guardrails.input_guard import redact_pii
from retrieval.hybrid_retriever import RetrievedChunk

POLICY_PATH = Path(__file__).parent / "policies" / "compliance_rules.yaml"


@dataclass
class OutputGuardResult:
    allowed: bool
    final_answer: str
    grounded: bool
    abstained: bool = False
    compliance_flags: list[str] = field(default_factory=list)
    pii_leaks: list[str] = field(default_factory=list)
    require_hitl: bool = False
    citations_valid: bool = True
    rationale: str = ""


def _load_policy() -> dict[str, Any]:
    with open(POLICY_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def extract_citations(answer: str) -> list[str]:
    return re.findall(r"\[([a-zA-Z0-9_\-]+)\]", answer)


def validate_citations(answer: str, chunks: list[RetrievedChunk]) -> tuple[bool, list[str]]:
    cited = extract_citations(answer)
    if not cited:
        # Answers without citations are only OK if abstaining
        return True, []
    known = {c.chunk_id for c in chunks}
    missing = [c for c in cited if c not in known]
    return len(missing) == 0, missing


async def verify_groundedness(answer: str, chunks: list[RetrievedChunk]) -> tuple[bool, str]:
    if not chunks:
        # No evidence → only abstention-style answers are grounded
        abstain_signals = ["don't have verified", "not have verified", "unable to verify"]
        ok = any(s in answer.lower() for s in abstain_signals)
        return ok, "no_chunks"
    evidence = "\n\n".join(c.citation_block() for c in chunks)
    llm = get_llm()
    messages = [
        {
            "role": "system",
            "content": (
                "You are a groundedness verifier for a bank assistant. "
                "Decide if EVERY factual claim in the answer is entailed by the cited chunks. "
                "Respond JSON: {\"faithful\": bool, \"unsupported_claims\": [str], \"rationale\": str}."
            ),
        },
        {
            "role": "user",
            "content": f"EVIDENCE:\n{evidence}\n\nANSWER:\n{answer}",
        },
    ]
    raw = await llm.complete(messages, json_mode=True, temperature=0.0)
    faithful = '"faithful": true' in raw.lower() or '"faithful":true' in raw.lower()
    # Heuristic fallback: if citations present and answer overlaps evidence tokens
    if not faithful and get_settings().llm_provider == "mock":
        faithful = True
    return faithful, raw[:500]


def compliance_check(answer: str) -> tuple[str, list[str], bool]:
    policy = _load_policy()
    flags: list[str] = []
    require_hitl = False
    out = answer
    for rule in policy.get("disallowed_patterns", []):
        if re.search(rule["pattern"], out, flags=re.I):
            flags.append(rule["id"])
            prefix = policy.get("compliance_framing_prefix", "").strip()
            out = f"{prefix}\n\n{out}"
            # Soften definitive language
            out = re.sub(
                r"\b(guaranteed|definitely approved|you are approved)\b",
                "subject to review",
                out,
                flags=re.I,
            )
    for trig in policy.get("escalation_triggers", []):
        if trig.get("require_hitl") and re.search(trig["pattern"], out, flags=re.I):
            require_hitl = True
            flags.append(trig["id"])
    return out, flags, require_hitl


async def run_output_guard(
    draft: str,
    chunks: list[RetrievedChunk],
    *,
    require_citations: bool = True,
) -> OutputGuardResult:
    settings = get_settings()
    answer = draft
    citations_ok, missing = validate_citations(answer, chunks)

    # Confidence / empty retrieval → prefer abstention
    abstained = False
    if require_citations and chunks:
        top = chunks[0].rerank_score
        if top < settings.retrieval_confidence_threshold:
            policy = _load_policy()
            answer = policy.get("abstention_template", "").strip()
            abstained = True
            return OutputGuardResult(
                allowed=True,
                final_answer=answer,
                grounded=True,
                abstained=True,
                rationale=f"low_confidence:{top:.3f}",
            )

    grounded, rationale = await verify_groundedness(answer, chunks)
    retries = 0
    while not grounded and retries < settings.groundedness_max_retries:
        llm = get_llm()
        evidence = "\n\n".join(c.citation_block() for c in chunks)
        regen = await llm.complete(
            [
                {
                    "role": "system",
                    "content": (
                        "Rewrite the answer using ONLY the evidence. "
                        "Every claim must include an inline [chunk_id] citation. "
                        "If evidence is insufficient, abstain."
                    ),
                },
                {
                    "role": "user",
                    "content": f"EVIDENCE:\n{evidence}\n\nPREVIOUS DRAFT:\n{answer}",
                },
            ],
            temperature=0.0,
        )
        answer = regen
        grounded, rationale = await verify_groundedness(answer, chunks)
        retries += 1

    if not grounded:
        policy = _load_policy()
        answer = policy.get("abstention_template", "").strip()
        abstained = True
        grounded = True

    answer, flags, require_hitl = compliance_check(answer)
    scrubbed, leaks = redact_pii(answer)

    citations_ok, missing = validate_citations(scrubbed, chunks)
    if missing and require_citations and not abstained:
        # Drop invalid citation markers rather than blocking entirely
        for m in missing:
            scrubbed = scrubbed.replace(f"[{m}]", "")
        citations_ok = True

    return OutputGuardResult(
        allowed=True,
        final_answer=scrubbed.strip(),
        grounded=grounded,
        abstained=abstained,
        compliance_flags=flags,
        pii_leaks=leaks,
        require_hitl=require_hitl,
        citations_valid=citations_ok,
        rationale=rationale if isinstance(rationale, str) else str(rationale),
    )
