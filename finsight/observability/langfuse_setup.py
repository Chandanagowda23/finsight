"""Optional Langfuse tracing — no-op when disabled or unconfigured."""

from __future__ import annotations

import structlog

from api.config import get_settings

log = structlog.get_logger(__name__)

_langfuse = None


def init_observability() -> None:
    global _langfuse
    s = get_settings()
    if not s.langfuse_enabled:
        log.info("langfuse_disabled")
        return
    try:
        from langfuse import Langfuse

        _langfuse = Langfuse(
            public_key=s.langfuse_public_key,
            secret_key=s.langfuse_secret_key,
            host=s.langfuse_host,
        )
        log.info("langfuse_initialized", host=s.langfuse_host)
    except Exception as e:
        log.warning("langfuse_init_failed", error=str(e))
        _langfuse = None


def get_langfuse():
    return _langfuse


def trace_event(name: str, metadata: dict | None = None) -> None:
    if _langfuse is None:
        return
    try:
        _langfuse.trace(name=name, metadata=metadata or {})
    except Exception as e:
        log.debug("langfuse_trace_failed", error=str(e))
