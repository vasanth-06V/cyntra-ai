import asyncio
import time
from collections import deque

from fastapi import HTTPException, status

# Requests per minute per user, deliberately a little under the free-tier
# caps (Gemini lite 15/min, embeddings 100/min) so a burst queues for a
# moment instead of being rejected with a 429. Process-local: correct for a
# single instance, which is how this runs.
DEFAULT_RPM: dict[str, int] = {
    "gemini": 12,
    "gemini:embed": 80,
    "claude": 40,
    "groq": 25,
}

MAX_WAIT_SECONDS = 20.0
_WINDOW_SECONDS = 60.0


class RateLimiter:
    def __init__(
        self,
        limits: dict[str, int] | None = None,
        clock=time.monotonic,
        sleep=asyncio.sleep,
        max_wait: float = MAX_WAIT_SECONDS,
    ):
        self._limits = DEFAULT_RPM if limits is None else limits
        self._clock = clock
        self._sleep = sleep
        self._max_wait = max_wait
        self._windows: dict[tuple[str, str], deque[float]] = {}
        self._locks: dict[tuple[str, str], asyncio.Lock] = {}

    async def acquire(self, user_id: str, bucket: str) -> None:
        """Waits for a free slot in this user's sliding one-minute window,
        or raises 429 if that would take longer than max_wait. Waiters for
        the same (user, bucket) queue in order behind a lock."""
        limit = self._limits.get(bucket)
        if not limit:
            return

        key = (user_id, bucket)
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            window = self._windows.setdefault(key, deque())
            waited = 0.0
            while True:
                now = self._clock()
                while window and now - window[0] >= _WINDOW_SECONDS:
                    window.popleft()
                if len(window) < limit:
                    window.append(now)
                    return

                wait = _WINDOW_SECONDS - (now - window[0])
                if waited + wait > self._max_wait:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Too many requests in a short time -- please wait a moment.",
                    )
                await self._sleep(wait)
                waited += wait


limiter = RateLimiter()
