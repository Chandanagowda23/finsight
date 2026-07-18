"""Pluggable LLM client — Ollama / Groq / Together / deterministic mock."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx
import structlog

from api.config import get_settings

log = structlog.get_logger(__name__)


class LLMClient:
    """Unified chat completion interface across free providers."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.provider = self.settings.llm_provider
        self.model = self.settings.llm_model

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.1,
        max_tokens: int = 1024,
        json_mode: bool = False,
    ) -> str:
        if self.provider == "mock":
            return self._mock_complete(messages, json_mode=json_mode)
        if self.provider == "ollama":
            return await self._ollama(messages, temperature, max_tokens, json_mode)
        if self.provider == "groq":
            return await self._openai_compat(
                "https://api.groq.com/openai/v1/chat/completions",
                self.settings.groq_api_key,
                messages,
                temperature,
                max_tokens,
                json_mode,
                model_override="llama-3.3-70b-versatile",
            )
        if self.provider == "together":
            return await self._openai_compat(
                "https://api.together.xyz/v1/chat/completions",
                self.settings.together_api_key,
                messages,
                temperature,
                max_tokens,
                json_mode,
                model_override="meta-llama/Llama-3.3-70B-Instruct-Turbo",
            )
        raise ValueError(f"Unknown LLM provider: {self.provider}")

    def complete_sync(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.1,
        max_tokens: int = 1024,
        json_mode: bool = False,
    ) -> str:
        if self.provider == "mock":
            return self._mock_complete(messages, json_mode=json_mode)
        # Sync path for Streamlit / scripts
        import asyncio

        return asyncio.get_event_loop().run_until_complete(
            self.complete(messages, temperature=temperature, max_tokens=max_tokens, json_mode=json_mode)
        )

    async def _ollama(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        json_mode: bool,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.model if self.model != "llama-3.1-8b" else "llama3.1:8b",
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if json_mode:
            payload["format"] = "json"
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(f"{self.settings.ollama_base_url}/api/chat", json=payload)
            r.raise_for_status()
            return r.json()["message"]["content"]

    async def _openai_compat(
        self,
        url: str,
        api_key: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        json_mode: bool,
        model_override: str | None = None,
    ) -> str:
        if not api_key:
            log.warning("api_key_missing_falling_back_to_mock", provider=self.provider)
            return self._mock_complete(messages, json_mode=json_mode)
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload: dict[str, Any] = {
            "model": model_override or self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]

    def _mock_complete(self, messages: list[dict[str, str]], *, json_mode: bool = False) -> str:
        """Deterministic, grounded mock for CI / offline demos — no network required."""
        user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        lower = user.lower()
        system_l = system.lower()

        # Intent classification
        if "classify" in system_l or "intent" in system_l:
            intent = self._classify_intent(lower)
            return json.dumps({"intent": intent, "confidence": 0.92, "rationale": "keyword heuristics"})

        # Groundedness check
        if "entailed" in system_l or "groundedness" in system_l or "faithful" in system_l:
            return json.dumps(
                {
                    "faithful": True,
                    "unsupported_claims": [],
                    "rationale": "All claims map to cited evidence in mock mode.",
                }
            )

        # Compliance rewrite
        if "compliance" in system_l and "rewrite" in system_l:
            return user  # pass-through

        # Extract context chunks from system prompt — keep full text for extractive QA
        chunks = re.findall(r"\[([a-zA-Z0-9_\-]+)\][^\n]*\n(.*?)(?=\n\[|\Z)", system, flags=re.S)
        if not chunks:
            chunks = re.findall(r"\[([a-zA-Z0-9_\-]+)\]\s*(.+?)(?=\n\[|\Z)", system, flags=re.S)
        citations = [c[0] for c in chunks[:5]] if chunks else []
        evidence_bits = [c[1].strip() for c in chunks[:5]] if chunks else []

        if "abstain" in system_l and ("low confidence" in lower or not chunks):
            return (
                "I don't have verified information on that in our current knowledge base. "
                "Please contact FinSight Support at 1-800-555-0199 or visit a branch for help."
            )

        answer = self._mock_answer(lower, evidence_bits, citations, system_l)
        return answer

    def _classify_intent(self, text: str) -> str:
        rules = [
            ("dispute", ["dispute", "complaint", "unauthorized charge", "chargeback", "fraudulent charge"]),
            ("fraud", ["fraud alert", "suspicious", "flagged transaction", "risk triage", "triage alert"]),
            ("account", ["my balance", "checking balance", "transaction history", "my card", "card status", "my account"]),
            (
                "eligibility",
                ["eligib", "pre-check", "precheck", "am i eligible", "qualify for a loan", "qualify for a card"],
            ),
            ("compliance", ["kyc", "cip", "aml policy", "internal policy", "sop", "beneficial owner", "sar filing"]),
            ("regulatory", ["circular", "reg e", "regulation", "cfpb", "basel"]),
            ("service_copilot", ["suggest response", "draft reply", "co-pilot", "help me reply"]),
            ("knowledge", ["fee", "apr", "rate", "policy", "terms", "what is", "how much", "apy", "cash back"]),
        ]
        for intent, kws in rules:
            if any(k in text for k in kws):
                return intent
        return "knowledge"

    def _mock_answer(
        self,
        query: str,
        evidence: list[str],
        citations: list[str],
        system_l: str,
    ) -> str:
        cite = " ".join(f"[{c}]" for c in citations) if citations else ""
        if evidence:
            # Prefer top-ranked evidence blocks; extractive sentence selection
            q_tokens = set(re.findall(r"[a-z0-9.%$]+", query.lower()))
            best_sents: list[tuple[float, str]] = []
            for bi, block in enumerate(evidence[:2]):
                rank_boost = 0.25 if bi == 0 else 0.0
                for sent in re.split(r"(?<=[.:;])\s+|\n+", block):
                    sent = sent.strip(" -*#")
                    if len(sent) < 20:
                        continue
                    s_tokens = set(re.findall(r"[a-z0-9.%$]+", sent.lower()))
                    if not s_tokens:
                        continue
                    overlap = len(q_tokens & s_tokens) / max(len(q_tokens), 1) + rank_boost
                    if re.search(r"\$|\d+%|\d+\.\d+", sent):
                        overlap += 0.2
                    best_sents.append((overlap, sent))
            best_sents.sort(key=lambda x: x[0], reverse=True)
            picked = [s for score, s in best_sents[:2] if score > 0.05]
            if not picked and evidence:
                picked = [evidence[0][:450]]
            body = " ".join(picked)
            return f"{body} {cite}".strip()
        if "eligib" in query:
            return (
                "This is an informational pre-check only — not a credit decision. "
                "Typical eligibility factors include income verification, credit history, "
                "and existing relationship tenure. A banker must complete a formal review. "
                f"{cite}"
            ).strip()
        if "dispute" in query:
            return (
                "I can help draft a dispute ticket for human review. "
                "Please share the transaction date, amount, merchant, and reason. "
                "No dispute will be filed until a specialist approves it. "
                f"{cite}"
            ).strip()
        if any(k in query for k in ("balance", "transaction", "card")):
            return "I'll look that up via our secure account tools and return verified details."
        return (
            "I can help with product information, account lookups, disputes, and policy questions. "
            "Please rephrase your question or specify the product. "
            f"{cite}"
        ).strip()


_client: LLMClient | None = None


def get_llm() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
