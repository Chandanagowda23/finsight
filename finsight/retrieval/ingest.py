"""Document → chunk → index pipeline."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import structlog
import yaml

from retrieval.chunking import chunk_document
from retrieval.hybrid_retriever import get_retriever

log = structlog.get_logger(__name__)

ROOT = Path(__file__).resolve().parents[1]
KB_ROOT = ROOT / "data" / "knowledge_base"


FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.S)


def parse_markdown(path: Path) -> tuple[dict, str]:
    raw = path.read_text(encoding="utf-8")
    m = FRONT_MATTER_RE.match(raw)
    if not m:
        return {
            "doc_id": path.stem,
            "title": path.stem.replace("_", " ").title(),
            "doc_type": "general",
            "effective_date": "2024-01-01",
            "access_role": "both",
            "source": str(path.relative_to(ROOT)),
        }, raw
    meta = yaml.safe_load(m.group(1)) or {}
    body = m.group(2)
    meta.setdefault("doc_id", path.stem)
    meta.setdefault("title", path.stem.replace("_", " ").title())
    meta.setdefault("source", str(path.relative_to(ROOT)))
    return meta, body


def load_all_documents() -> list[dict]:
    payloads: list[dict] = []
    for path in sorted(KB_ROOT.rglob("*.md")):
        meta, body = parse_markdown(path)
        chunks = chunk_document(
            doc_id=meta["doc_id"],
            title=meta["title"],
            body=body,
            doc_type=meta.get("doc_type", "general"),
            effective_date=str(meta.get("effective_date", "2024-01-01")),
            access_role=meta.get("access_role", "both"),
            source=meta.get("source", str(path)),
        )
        for c in chunks:
            payload = c.to_payload()
            if meta.get("superseded_by"):
                payload["superseded_by"] = meta["superseded_by"]
            payloads.append(payload)
        log.info("chunked_doc", path=str(path), chunks=len(chunks))
    return payloads


def ingest(reset: bool = False) -> int:
    retriever = get_retriever()
    if reset:
        retriever.memory.chunks = []
        retriever.memory.vectors = None
        retriever.memory._bm25 = None
    payloads = load_all_documents()
    n = retriever.index(payloads)
    log.info("ingest_complete", chunks=n)
    return n


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest FinSight knowledge base")
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    n = ingest(reset=args.reset)
    print(f"Indexed {n} chunks")


if __name__ == "__main__":
    main()
