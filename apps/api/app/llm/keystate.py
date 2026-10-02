"""Per-key bookkeeping that must outlive a single request.

Provider quotas belong to a *key's project*, not to our user, so rate limits
and "this key is spent" cooldowns are tracked by a non-reversible fingerprint
of the key. (A user's backup key from a different project then gets its own
budget; two users who share a key share its limits, which is what the
provider enforces too.) The key itself is never stored or logged.
"""

import hashlib
import time
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo


def key_hash(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()[:16]


def seconds_until_pacific_midnight(now: datetime | None = None) -> float:
    """Google's daily (RPD) quotas reset at midnight Pacific time."""
    now = now or datetime.now(UTC)
    try:
        pacific = now.astimezone(ZoneInfo("America/Los_Angeles"))
    except Exception:  # tz database missing (e.g. a bare Windows install)
        pacific = now.astimezone(UTC) - timedelta(hours=8)
    tomorrow = (pacific + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(60.0, (tomorrow - pacific).total_seconds())


class KeyCooldowns:
    """Remembers keys the provider just told us are out of quota, so we skip
    straight to the backup instead of re-probing a spent key on every call."""

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._until: dict[tuple[str, str], float] = {}

    def set(self, provider: str, khash: str, seconds: float) -> None:
        self._until[(provider, khash)] = self._clock() + max(1.0, seconds)

    def remaining(self, provider: str, khash: str) -> float:
        until = self._until.get((provider, khash), 0.0)
        left = until - self._clock()
        if left <= 0:
            self._until.pop((provider, khash), None)
            return 0.0
        return left

    def forget(self, provider: str, khash: str) -> None:
        self._until.pop((provider, khash), None)

    def clear(self) -> None:
        self._until.clear()


cooldowns = KeyCooldowns()
