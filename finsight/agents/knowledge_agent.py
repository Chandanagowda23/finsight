"""Knowledge / RAG agent — hybrid retrieve → confidence gate → cite → generate."""

from __future__ import annotations

from typing import Any

from agents.state import AgentState
from api.config import get_settings
from api.llm import get_llm
from guardrails.output_guard import run_output_guard
from retrieval.hybrid_retriever import RetrievedChunk, get_retriever


def _chunks_from_state(state: AgentState) -> list[RetrievedChunk]:
    out = []
    for c in state.get("retrieved_chunks") or []:
        out.append(
            RetrievedChunk(
                chunk_id=c["chunk_id"],
                text=c["text"],
                title=c.get("title", ""),
                doc_type=c.get("doc_type", ""),
                effective_date=c.get("effective_date", ""),
                access_role=c.get("access_role", ""),
                source=c.get("source", ""),
                section=c.get("section", ""),
                score=float(c.get("score", 0)),
                rerank_score=float(c.get("rerank_score", 0)),
            )
        )
    return out


async def knowledge_retrieve(state: AgentState) -> dict[str, Any]:
    role = state.get("role", "customer")
    access = "staff" if role == "staff" else "customer"
    query = state.get("redacted_message") or state["user_message"]
    retriever = get_retriever()
    if not retriever._ready and not retriever.memory.chunks:
        from retrieval.ingest import ingest

        ingest()
    chunks = retriever.retrieve(query, access_role=access)
    return {
        "retrieved_chunks": [
            {
                "chunk_id": c.chunk_id,
                "text": c.text,
                "title": c.title,
                "doc_type": c.doc_type,
                "effective_date": c.effective_date,
                "access_role": c.access_role,
                "source": c.source,
                "section": c.section,
                "score": c.score,
                "rerank_score": c.rerank_score,
            }
            for c in chunks
        ],
        "confidence": chunks[0].rerank_score if chunks else 0.0,
        "trace": [{"step": "knowledge_retrieve", "n_chunks": len(chunks)}],
    }


async def knowledge_generate(state: AgentState) -> dict[str, Any]:
    settings = get_settings()
    chunks = _chunks_from_state(state)
    query = state.get("redacted_message") or state["user_message"]

    if not chunks or (chunks and chunks[0].rerank_score < settings.retrieval_confidence_threshold):
        from pathlib import Path

        import yaml

        policy = yaml.safe_load(
            (Path(__file__).resolve().parents[1] / "guardrails/policies/compliance_rules.yaml").read_text()
        )
        abstain = policy.get("abstention_template", "").strip()
        return {
            "draft_answer": abstain,
            "final_answer": abstain,
            "abstained": True,
            "grounded": True,
            "citations": [],
            "trace": [{"step": "knowledge_abstain", "reason": "low_confidence"}],
        }

    evidence = "\n\n".join(c.citation_block() for c in chunks)
    llm = get_llm()
    draft = await llm.complete(
        [
            {
                "role": "system",
                "content": (
                    "You are FinSight Knowledge Agent for a bank. "
                    "Answer ONLY using the evidence below. "
                    "Cite every factual claim with inline [chunk_id]. "
                    "If evidence is insufficient, say you don't have verified information.\n\n"
                    f"EVIDENCE:\n{evidence}"
                ),
            },
            {"role": "user", "content": query},
        ],
        temperature=0.1,
    )

    guard = await run_output_guard(draft, chunks, require_citations=True)
    return {
        "draft_answer": draft,
        "final_answer": guard.final_answer,
        "abstained": guard.abstained,
        "grounded": guard.grounded,
        "require_hitl": guard.require_hitl,
        "compliance_flags": guard.compliance_flags,
        "citations": [c.chunk_id for c in chunks],
        "trace": [
            {
                "step": "knowledge_generate",
                "grounded": guard.grounded,
                "abstained": guard.abstained,
                "flags": guard.compliance_flags,
            }
        ],
    }


async def run_knowledge_agent(state: AgentState) -> dict[str, Any]:
    mid = await knowledge_retrieve(state)
    merged = {**state, **mid}
    gen = await knowledge_generate(merged)
    # Only emit *new* trace steps — LangGraph appends via Annotated reducer
    new_trace = list(mid.get("trace") or []) + list(gen.get("trace") or [])
    return {**mid, **gen, "trace": new_trace}
