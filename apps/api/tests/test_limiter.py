import pytest
from fastapi import HTTPException

from app.llm.limiter import RateLimiter


class FakeTime:
    """A controllable clock; sleeping just advances it."""

    def __init__(self):
        self.now = 1000.0
        self.slept: list[float] = []

    def clock(self):
        return self.now

    async def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


def _limiter(t: FakeTime, rpm: int = 3, max_wait: float = 20.0) -> RateLimiter:
    return RateLimiter(limits={"gemini": rpm}, clock=t.clock, sleep=t.sleep, max_wait=max_wait)


@pytest.mark.asyncio
async def test_requests_under_the_limit_pass_without_waiting():
    t = FakeTime()
    limiter = _limiter(t, rpm=3)

    for _ in range(3):
        await limiter.acquire("u1", "gemini")

    assert t.slept == []


@pytest.mark.asyncio
async def test_a_burst_over_the_limit_waits_for_the_window_instead_of_failing():
    t = FakeTime()
    limiter = _limiter(t, rpm=2, max_wait=120)

    await limiter.acquire("u1", "gemini")
    t.now += 10
    await limiter.acquire("u1", "gemini")
    await limiter.acquire("u1", "gemini")  # third within a minute

    # It had to wait until the first request aged out of the 60s window.
    assert t.slept == [pytest.approx(50.0)]


@pytest.mark.asyncio
async def test_raises_429_when_the_wait_would_be_too_long():
    t = FakeTime()
    limiter = _limiter(t, rpm=1, max_wait=20)

    await limiter.acquire("u1", "gemini")
    with pytest.raises(HTTPException) as exc:
        await limiter.acquire("u1", "gemini")  # needs ~60s, cap is 20s

    assert exc.value.status_code == 429
    assert t.slept == []  # refused up front rather than sleeping then failing


@pytest.mark.asyncio
async def test_users_have_independent_buckets():
    t = FakeTime()
    limiter = _limiter(t, rpm=1)

    await limiter.acquire("u1", "gemini")
    await limiter.acquire("u2", "gemini")  # different user: no wait

    assert t.slept == []


@pytest.mark.asyncio
async def test_old_requests_age_out_of_the_window():
    t = FakeTime()
    limiter = _limiter(t, rpm=1)

    await limiter.acquire("u1", "gemini")
    t.now += 61
    await limiter.acquire("u1", "gemini")

    assert t.slept == []


@pytest.mark.asyncio
async def test_unknown_buckets_are_not_limited():
    t = FakeTime()
    limiter = _limiter(t, rpm=1)

    for _ in range(5):
        await limiter.acquire("u1", "some-other-provider")

    assert t.slept == []
