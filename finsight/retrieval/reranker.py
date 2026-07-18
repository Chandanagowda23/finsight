"""Cross-encoder reranker with lexical fallback."""

from __future__ import annotations

import structlog

from api.config import get_settings
from retrieval.embeddings import lexical_overlap_score

log = structlog.get_logger(__name__)

_reranker = None


def _get_reranker():
    global _reranker
    settings = get_settings()
    if settings.lightweight_mode:
        return None
    if _reranker is None:
        try:
            from sentence_transformers import CrossEncoder

            log.info("loading_reranker", model=settings.reranker_model)
            _reranker = CrossEncoder(settings.reranker_model)
        except Exception as e:
            log.warning("reranker_load_failed", error=str(e))
            _reranker = None
    return _reranker


def rerank(query: str, candidates: list[dict], top_k: int | None = None) -> list[dict]:
    """Each candidate: {chunk_id, text, score, ...}. Returns scored+sorted list."""
    if not candidates:
        return []
    settings = get_settings()
    top_k = top_k or settings.rerank_top_k
    model = _get_reranker()

    if model is None:
        scored = []
        for c in candidates:
            lex = lexical_overlap_score(query, c.get("text", ""))
            fused = 0.6 * float(c.get("score", 0.0)) + 0.4 * lex
            scored.append({**c, "rerank_score": fused})
        scored.sort(key=lambda x: x["rerank_score"], reverse=True)
        return scored[:top_k]

    pairs = [[query, c.get("text", "")] for c in candidates]
    scores = model.predict(pairs)
    scored = [{**c, "rerank_score": float(s)} for c, s in zip(candidates, scores, strict=False)]
    scored.sort(key=lambda x: x["rerank_score"], reverse=True)
    return scored[:top_k]
