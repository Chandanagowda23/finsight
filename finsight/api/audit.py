"""Append-only audit log — SQLite by default, Postgres in Docker."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Column, DateTime, String, Text, create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from api.config import get_settings


class Base(DeclarativeBase):
    pass


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(String(36), primary_key=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    actor = Column(String(128), nullable=False)
    role = Column(String(32), nullable=False)
    event_type = Column(String(64), nullable=False)
    session_id = Column(String(64), nullable=True)
    payload_json = Column(Text, nullable=False)


class HITLQueueItem(Base):
    __tablename__ = "hitl_queue"

    id = Column(String(36), primary_key=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(32), nullable=False, default="pending")  # pending|approved|rejected
    kind = Column(String(64), nullable=False)
    actor = Column(String(128), nullable=False)
    summary = Column(Text, nullable=False)
    payload_json = Column(Text, nullable=False)
    reviewer = Column(String(128), nullable=True)
    review_notes = Column(Text, nullable=True)


_engine = None
_SessionLocal = None


def _make_engine():
    s = get_settings()
    url = s.database_url_sync
    if s.use_sqlite or url.startswith("sqlite"):
        Path("data").mkdir(parents=True, exist_ok=True)
        eng = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(eng, "connect")
        def _set_sqlite_pragma(dbapi_conn, _):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

        return eng
    return create_engine(url)


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        _engine = _make_engine()
        Base.metadata.create_all(_engine)
        # Append-only trigger for SQLite (best-effort)
        if get_settings().use_sqlite:
            with _engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        CREATE TRIGGER IF NOT EXISTS audit_no_update
                        BEFORE UPDATE ON audit_events
                        BEGIN
                          SELECT RAISE(ABORT, 'audit_events is append-only');
                        END;
                        """
                    )
                )
                conn.execute(
                    text(
                        """
                        CREATE TRIGGER IF NOT EXISTS audit_no_delete
                        BEFORE DELETE ON audit_events
                        BEGIN
                          SELECT RAISE(ABORT, 'audit_events is append-only');
                        END;
                        """
                    )
                )
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    return _engine


def get_session() -> Session:
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal()


def write_audit(
    *,
    actor: str,
    role: str,
    event_type: str,
    payload: dict[str, Any],
    session_id: str | None = None,
) -> str:
    event_id = str(uuid.uuid4())
    with get_session() as db:
        db.add(
            AuditEvent(
                id=event_id,
                created_at=datetime.now(UTC),
                actor=actor,
                role=role,
                event_type=event_type,
                session_id=session_id,
                payload_json=json.dumps(payload, default=str),
            )
        )
        db.commit()
    return event_id


def enqueue_hitl(*, kind: str, actor: str, summary: str, payload: dict[str, Any]) -> str:
    item_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    with get_session() as db:
        db.add(
            HITLQueueItem(
                id=item_id,
                created_at=now,
                updated_at=now,
                status="pending",
                kind=kind,
                actor=actor,
                summary=summary,
                payload_json=json.dumps(payload, default=str),
            )
        )
        db.commit()
    write_audit(
        actor=actor,
        role="system",
        event_type="hitl_enqueued",
        payload={"hitl_id": item_id, "kind": kind, "summary": summary},
    )
    return item_id


def list_hitl(status: str | None = "pending") -> list[dict[str, Any]]:
    with get_session() as db:
        q = db.query(HITLQueueItem)
        if status:
            q = q.filter(HITLQueueItem.status == status)
        rows = q.order_by(HITLQueueItem.created_at.desc()).limit(100).all()
        return [
            {
                "id": r.id,
                "created_at": r.created_at.isoformat(),
                "status": r.status,
                "kind": r.kind,
                "actor": r.actor,
                "summary": r.summary,
                "payload": json.loads(r.payload_json),
                "reviewer": r.reviewer,
                "review_notes": r.review_notes,
            }
            for r in rows
        ]


def resolve_hitl(item_id: str, *, reviewer: str, approve: bool, notes: str = "") -> dict[str, Any]:
    with get_session() as db:
        row = db.query(HITLQueueItem).filter(HITLQueueItem.id == item_id).first()
        if not row:
            raise ValueError("HITL item not found")
        row.status = "approved" if approve else "rejected"
        row.reviewer = reviewer
        row.review_notes = notes
        row.updated_at = datetime.now(UTC)
        db.commit()
        result = {
            "id": row.id,
            "status": row.status,
            "kind": row.kind,
            "payload": json.loads(row.payload_json),
        }
    write_audit(
        actor=reviewer,
        role="staff",
        event_type="hitl_resolved",
        payload={"hitl_id": item_id, "approved": approve, "notes": notes},
    )
    return result
