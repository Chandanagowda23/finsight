"""Semantic-ish chunking with banking metadata tags."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    title: str
    text: str
    doc_type: str
    effective_date: str
    access_role: str  # customer | staff | both
    source: str
    section: str = ""
    superseded_by: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)

    def is_active_on(self, as_of: date | None = None) -> bool:
        if self.superseded_by:
            return False
        as_of = as_of or date.today()
        try:
            eff = date.fromisoformat(self.effective_date)
        except ValueError:
            return True
        return eff <= as_of


def _stable_id(doc_id: str, idx: int, text: str) -> str:
    h = hashlib.sha1(f"{doc_id}:{idx}:{text[:64]}".encode()).hexdigest()[:10]
    return f"{doc_id}__c{idx}_{h}"


def chunk_document(
    *,
    doc_id: str,
    title: str,
    body: str,
    doc_type: str,
    effective_date: str,
    access_role: str,
    source: str,
    max_chars: int = 700,
    overlap: int = 80,
) -> list[Chunk]:
    """Split on headings / paragraphs, then pack into size-bounded chunks."""
    # Split on markdown headings or double newlines
    parts = re.split(r"(?=\n#{1,3}\s)|\n{2,}", body.strip())
    parts = [p.strip() for p in parts if p and p.strip()]
    if not parts:
        parts = [body.strip()]

    packed: list[tuple[str, str]] = []
    buf = ""
    section = title
    for part in parts:
        heading = re.match(r"^#{1,3}\s+(.+)$", part.split("\n", 1)[0])
        if heading:
            section = heading.group(1).strip()
        if len(buf) + len(part) + 1 <= max_chars:
            buf = f"{buf}\n{part}".strip()
        else:
            if buf:
                packed.append((section, buf))
            if len(part) <= max_chars:
                buf = part
            else:
                # hard wrap long sections
                start = 0
                while start < len(part):
                    end = min(start + max_chars, len(part))
                    packed.append((section, part[start:end]))
                    start = max(end - overlap, end)
                buf = ""
    if buf:
        packed.append((section, buf))

    chunks: list[Chunk] = []
    for i, (section, text) in enumerate(packed):
        chunks.append(
            Chunk(
                chunk_id=_stable_id(doc_id, i, text),
                doc_id=doc_id,
                title=title,
                text=text,
                doc_type=doc_type,
                effective_date=effective_date,
                access_role=access_role,
                source=source,
                section=section,
            )
        )
    return chunks
