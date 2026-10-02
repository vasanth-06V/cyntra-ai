import time
from collections.abc import Callable


class TTLCache:
    """Tiny in-process cache. Memory only (nothing persisted), bounded in size."""

    def __init__(self, ttl_seconds: float, max_items: int = 256, clock: Callable[[], float] = time.monotonic):
        self._ttl = ttl_seconds
        self._max = max_items
        self._clock = clock
        self._data: dict = {}

    def get(self, key):
        entry = self._data.get(key)
        if entry is None:
            return None
        expires, value = entry
        if self._clock() >= expires:
            del self._data[key]
            return None
        return value

    def set(self, key, value) -> None:
        if len(self._data) >= self._max:
            self._data.pop(next(iter(self._data)))
        self._data[key] = (self._clock() + self._ttl, value)
