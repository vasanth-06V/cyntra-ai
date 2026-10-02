"""Per-user request throttles for endpoints that cost real money or CPU
(key validation hits a provider, ATS/RAG/interview-start run LLM + embedding
work). Unlike llm/limiter.py, which *queues* to stay inside a provider's
quota, this rejects immediately with a Retry-After: it exists to stop abuse
and runaway clients, not to smooth bursts.

In-process and per-instance, which matches the single-instance deployment.
"""

import math
import time
from collections import deque

from fastapi import Depends

from app.core.errors import AppError
from app.core.security import AuthenticatedUser, get_current_user

_EVICT_EVERY = 256


class Throttle:
    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._hits: dict[tuple[str, str], deque[float]] = {}
        self._checks = 0

    def reset(self) -> None:
        self._hits.clear()
        self._checks = 0

    def check(self, user_id: str, bucket: str, limit: int, per: float = 60.0) -> None:
        now = self._clock()
        hits = self._hits.setdefault((user_id, bucket), deque())
        while hits and now - hits[0] >= per:
            hits.popleft()

        if len(hits) >= limit:
            retry_after = max(1, math.ceil(per - (now - hits[0])))
            raise AppError(
                429,
                "rate_limited",
                f"Too many requests -- please wait {retry_after}s and try again.",
                headers={"Retry-After": str(retry_after)},
            )
        hits.append(now)

        self._checks += 1
        if self._checks % _EVICT_EVERY == 0:
            self._evict(now, per)

    def _evict(self, now: float, per: float) -> None:
        # Drop users who have been quiet for a full window so the dict can't grow forever.
        for key in [k for k, h in self._hits.items() if not h or now - h[-1] >= per]:
            del self._hits[key]


throttle = Throttle()


def limited(bucket: str, limit: int, per: float = 60.0):
    """FastAPI dependency: authenticates, then enforces `limit` calls per
    `per` seconds for this user and bucket. Returns the user."""

    async def dependency(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        throttle.check(user.user_id, bucket, limit, per)
        return user

    return dependency
