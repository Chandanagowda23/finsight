"""Hybrid retriever: BM25 + dense → merge → cross-encoder rerank → top-k."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

import numpy as np
import structlog
from rank_bm25 import BM25Okapi

from api.config import get_settings
from retrieval.embeddings import embed_query, embed_texts
from retrieval.reranker import rerank

log = structlog.get_logger(__name__)

AccessRole = Literal["customer", "staff", "both"]


@dataclass
class RetrievedChunk:
    chunk_id: str
    text: str
    title: str
    doc_type: str
    effective_date: str
    access_role: str
    source: str
    section: str
    score: float
    rerank_score: float

    def citation_block(self) -> str:
        return f"[{self.chunk_id}] ({self.title} · effective {self.effective_date})\n{self.text}"


class InMemoryStore:
    """Fallback vector+payload store when Qdrant is unavailable."""

    def __init__(self) -> None:
        self.chunks: list[dict[str, Any]] = []
        self.vectors: np.ndarray | None = None
        self._bm25: BM25Okapi | None = None
        self._tokenized: list[list[str]] = []

    def upsert(self, payloads: list[dict[str, Any]], vectors: np.ndarray) -> None:
        self.chunks.extend(payloads)
        if self.vectors is None:
            self.vectors = vectors
        else:
            self.vectors = np.vstack([self.vectors, vectors])
        self._rebuild_bm25()

    def _rebuild_bm25(self) -> None:
        self._tokenized = [c["text"].lower().split() for c in self.chunks]
        self._bm25 = BM25Okapi(self._tokenized) if self._tokenized else None

    def search_dense(self, query_vec: np.ndarray, top_k: int, filt: dict) -> list[dict]:
        if self.vectors is None or len(self.chunks) == 0:
            return []
        sims = self.vectors @ query_vec
        idxs = np.argsort(-sims)[: top_k * 3]
        out = []
        for i in idxs:
            payload = self.chunks[int(i)]
            if not _passes_filter(payload, filt):
                continue
            out.append({**payload, "score": float(sims[int(i)])})
            if len(out) >= top_k:
                break
        return out

    def search_bm25(self, query: str, top_k: int, filt: dict) -> list[dict]:
        if not self._bm25:
            return []
        scores = self._bm25.get_scores(query.lower().split())
        idxs = np.argsort(-scores)[: top_k * 3]
        out = []
        for i in idxs:
            payload = self.chunks[int(i)]
            if not _passes_filter(payload, filt):
                continue
            out.append({**payload, "score": float(scores[int(i)])})
            if len(out) >= top_k:
                break
        return out


def _passes_filter(payload: dict, filt: dict) -> bool:
    role = filt.get("access_role")
    if role:
        allowed = payload.get("access_role", "both")
        if allowed not in (role, "both"):
            return False
    as_of = filt.get("as_of")
    if as_of and payload.get("superseded_by"):
        return False
    if as_of:
        try:
            if date.fromisoformat(payload["effective_date"]) > as_of:
                return False
        except (KeyError, ValueError):
            pass
    doc_types = filt.get("doc_types")
    if doc_types and payload.get("doc_type") not in doc_types:
        return False
    return True


class HybridRetriever:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.memory = InMemoryStore()
        self._qdrant = None
        self._ready = False

    def _try_qdrant(self):
        if self.settings.qdrant_in_memory:
            return None
        if self._qdrant is not None:
            return self._qdrant
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.http import models as qm

            client = QdrantClient(url=self.settings.qdrant_url, timeout=5)
            # probe
            client.get_collections()
            self._qdrant = (client, qm)
            return self._qdrant
        except Exception as e:
            log.warning("qdrant_unavailable_using_memory", error=str(e))
            return None

    def index(self, payloads: list[dict[str, Any]]) -> int:
        if not payloads:
            return 0
        vectors = embed_texts([p["text"] for p in payloads])
        q = self._try_qdrant()
        if q:
            client, qm = q
            dim = vectors.shape[1]
            name = self.settings.qdrant_collection
            existing = [c.name for c in client.get_collections().collections]
            if name not in existing:
                client.create_collection(
                    collection_name=name,
                    vectors_config=qm.VectorParams(size=dim, distance=qm.Distance.COSINE),
                )
            points = [
                qm.PointStruct(
                    id=abs(hash(p["chunk_id"])) % (2**63),
                    vector=vectors[i].tolist(),
                    payload=p,
                )
                for i, p in enumerate(payloads)
            ]
            client.upsert(collection_name=name, points=points)
        # Always keep memory mirror for BM25 + offline
        self.memory.upsert(payloads, vectors)
        self._ready = True
        return len(payloads)

    def retrieve(
        self,
        query: str,
        *,
        access_role: str = "customer",
        as_of: date | None = None,
        doc_types: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        settings = self.settings
        filt = {
            "access_role": access_role,
            "as_of": as_of or date.today(),
            "doc_types": doc_types,
        }

        # Dense
        qvec = embed_query(query)
        dense_hits = self.memory.search_dense(qvec, settings.dense_top_k, filt)

        # Also try Qdrant dense if available
        q = self._try_qdrant()
        if q:
            client, qm = q
            try:
                must = []
                if access_role == "customer":
                    must.append(
                        qm.FieldCondition(
                            key="access_role",
                            match=qm.MatchAny(any=["customer", "both"]),
                        )
                    )
                elif access_role == "staff":
                    must.append(
                        qm.FieldCondition(
                            key="access_role",
                            match=qm.MatchAny(any=["staff", "both"]),
                        )
                    )
                qfilter = qm.Filter(must=must) if must else None
                results = client.search(
                    collection_name=settings.qdrant_collection,
                    query_vector=qvec.tolist(),
                    query_filter=qfilter,
                    limit=settings.dense_top_k,
                )
                dense_hits = [
                    {**r.payload, "score": float(r.score)} for r in results if r.payload
                ]
            except Exception as e:
                log.warning("qdrant_search_failed", error=str(e))

        sparse_hits = self.memory.search_bm25(query, settings.bm25_top_k, filt)

        # RRF merge
        merged: dict[str, dict] = {}
        for rank, hit in enumerate(dense_hits):
            cid = hit["chunk_id"]
            merged.setdefault(cid, {**hit, "score": 0.0})
            merged[cid]["score"] += 1.0 / (60 + rank)
        for rank, hit in enumerate(sparse_hits):
            cid = hit["chunk_id"]
            merged.setdefault(cid, {**hit, "score": 0.0})
            merged[cid]["score"] += 1.0 / (60 + rank)

        candidates = list(merged.values())
        reranked = rerank(query, candidates, top_k=settings.rerank_top_k)

        return [
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
            for c in reranked
        ]


_retriever: HybridRetriever | None = None


def get_retriever() -> HybridRetriever:
    global _retriever
    if _retriever is None:
        _retriever = HybridRetriever()
    return _retriever
