import pytest

from app.core.errors import AppError
from app.core.throttle import Throttle


def test_rejects_once_the_limit_is_hit_with_a_retry_after():
    now = [0.0]
    t = Throttle(clock=lambda: now[0])
    for _ in range(3):
        t.check("u", "ats", 3)
    with pytest.raises(AppError) as exc:
        t.check("u", "ats", 3)
    assert exc.value.status_code == 429 and exc.value.code == "rate_limited"
    assert int(exc.value.headers["Retry-After"]) >= 1


def test_window_slides_and_users_and_buckets_are_independent():
    now = [0.0]
    t = Throttle(clock=lambda: now[0])
    for _ in range(2):
        t.check("u", "a", 2)
    t.check("other-user", "a", 2)  # another user is unaffected
    t.check("u", "b", 2)  # another bucket is unaffected
    with pytest.raises(AppError):
        t.check("u", "a", 2)
    now[0] = 61
    t.check("u", "a", 2)  # window has passed


def test_idle_users_are_evicted_so_memory_stays_bounded():
    now = [0.0]
    t = Throttle(clock=lambda: now[0])
    for i in range(255):
        t.check(f"user-{i}", "a", 5)
    now[0] = 1000
    t.check("late-user", "a", 5)  # 256th check triggers eviction
    assert len(t._hits) == 1


@pytest.mark.asyncio
async def test_limiter_evicts_idle_windows():
    from app.llm.limiter import RateLimiter

    now = [0.0]
    lim = RateLimiter(limits={"gemini": 100}, clock=lambda: now[0], sleep=lambda s: None)
    for i in range(255):
        await lim.acquire(f"user-{i}", "gemini")
    now[0] = 1000
    await lim.acquire("late-user", "gemini")
    assert len(lim._windows) == 1


def test_the_expensive_endpoints_are_actually_throttled(monkeypatch):
    from fastapi.testclient import TestClient

    from app.core.security import AuthenticatedUser, get_current_user
    from app.main import app

    async def fake_submit_key(**kwargs):  # never reach a real provider from a test
        return {"id": "k", "provider": "gemini", "slot": "primary", "is_valid": True, "last_validated_at": None}

    monkeypatch.setattr("app.keys.router.service.submit_key", fake_submit_key)
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser("throttle-user", "a@b.c")
    try:
        client = TestClient(app)
        body = {"provider": "gemini", "slot": "primary", "api_key": "x" * 8}
        statuses = [client.post("/keys", json=body).status_code for _ in range(12)]
    finally:
        app.dependency_overrides.clear()
    assert 429 in statuses  # the 11th call within the minute is refused
