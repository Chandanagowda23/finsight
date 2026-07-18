"""Embedding models with lightweight lexical fallback for CPU-only / CI."""

from __future__ import annotations

import hashlib
import math
import re
from functools import lru_cache

import numpy as np
import structlog

from api.config import get_settings

log = structlog.get_logger(__name__)

_model = None
_DIM = 384


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _hash_embed(text: str, dim: int = _DIM) -> np.ndarray:
    """Deterministic bag-of-tokens hashing trick — no model download required."""
    vec = np.zeros(dim, dtype=np.float32)
    tokens = _tokenize(text)
    if not tokens:
        return vec
    for tok in tokens:
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if (h >> 8) % 2 == 0 else -1.0
        vec[idx] += sign
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm
    return vec


def get_embedding_model():
    global _model
    settings = get_settings()
    if settings.lightweight_mode:
        return None
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer

            log.info("loading_embedding_model", model=settings.embedding_model)
            _model = SentenceTransformer(settings.embedding_model)
        except Exception as e:
            log.warning("embedding_model_load_failed_using_hash", error=str(e))
            _model = None
    return _model


def embed_texts(texts: list[str]) -> np.ndarray:
    model = get_embedding_model()
    if model is None:
        return np.vstack([_hash_embed(t) for t in texts])
    return np.asarray(model.encode(texts, normalize_embeddings=True), dtype=np.float32)


def embed_query(text: str) -> np.ndarray:
    return embed_texts([text])[0]


@lru_cache(maxsize=1)
def embedding_dim() -> int:
    model = get_embedding_model()
    if model is None:
        return _DIM
    return int(model.get_sentence_embedding_dimension())


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def lexical_overlap_score(query: str, doc: str) -> float:
    q = set(_tokenize(query))
    d = set(_tokenize(doc))
    if not q or not d:
        return 0.0
    return len(q & d) / math.sqrt(len(q) * len(d))
