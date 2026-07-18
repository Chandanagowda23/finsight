"""Simple in-memory rate limiter (SlowAPI-compatible semantics)."""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from api.config import get_settings


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        limit = get_settings().rate_limit_per_minute
        now = time.time()
        window = 60.0
        q = self._hits[key]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Please try again shortly.")
        q.append(now)


limiter = RateLimiter()


async def rate_limit_dependency(request: Request) -> None:
    client = request.client.host if request.client else "unknown"
    auth = request.headers.get("authorization", "")
    key = f"{client}:{auth[:32]}"
    limiter.check(key)
