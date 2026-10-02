import asyncio
import time
from collections import deque

from fastapi import HTTPException, status

from app.core.errors import AppError

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
        self._acquires = 0

    async def acquire(self, owner: str, bucket: str, priority: str = "interactive") -> None:
        """Waits for a free slot in this owner's sliding one-minute window
        (owner = a key fingerprint: quotas belong to the key's project), or
        raises 429 if that would take longer than max_wait. Waiters for the
        same (owner, bucket) queue in order behind a lock.

        "background" callers (summaries, digests) may not use the last
        quarter of the window, so a user's live turn never waits behind them."""
        limit = self._limits.get(bucket)
        if not limit:
            return

        self._acquires += 1
        if self._acquires % 256 == 0:
            self._evict_idle()

        key = (owner, bucket)
        ceiling = limit if priority != "background" else max(1, limit - max(1, limit // 4))
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            window = self._windows.setdefault(key, deque())
            waited = 0.0
            while True:
                now = self._clock()
                while window and now - window[0] >= _WINDOW_SECONDS:
                    window.popleft()
                if len(window) < ceiling:
                    window.append(now)
                    return

                wait = _WINDOW_SECONDS - (now - window[0])
                if waited + wait > self._max_wait:
                    raise AppError(status.HTTP_429_TOO_MANY_REQUESTS, "rate_limited", "Too many requests in a short time -- please wait a moment.")
                await self._sleep(wait)
                waited += wait

    def _evict_idle(self) -> None:
        """Forget users who have been quiet for a full window (and aren't
        mid-wait), so the per-user dicts can't grow without bound."""
        now = self._clock()
        for key in list(self._windows):
            window = self._windows[key]
            lock = self._locks.get(key)
            quiet = not window or now - window[-1] >= _WINDOW_SECONDS
            if quiet and not (lock and lock.locked()):
                self._windows.pop(key, None)
                self._locks.pop(key, None)


limiter = RateLimiter()
