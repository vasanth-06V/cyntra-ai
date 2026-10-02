import pytest

from app.db import usage as usage_repo
from app.llm import usage
from app.llm.options import Usage


class _FakeSupabase:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.rpc_calls: list[tuple[str, dict]] = []

    def rpc(self, name, params):
        self.rpc_calls.append((name, params))
        fake = self

        class _Call:
            def execute(self):
                if fake.error:
                    raise fake.error

        return _Call()


@pytest.mark.asyncio
async def test_records_provider_reported_counts(monkeypatch):
    fake = _FakeSupabase()
    monkeypatch.setattr(usage_repo, "get_supabase", lambda: fake)

    await usage.record("u1", "gemini", "chat", Usage(requests=1, input_tokens=120, output_tokens=30))

    name, params = fake.rpc_calls[0]
    assert name == "record_llm_usage"
    assert params == {
        "p_user_id": "u1",
        "p_provider": "gemini",
        "p_kind": "chat",
        "p_requests": 1,
        "p_input": 120,
        "p_output": 30,
    }


@pytest.mark.asyncio
async def test_falls_back_to_estimates_when_the_provider_reported_no_tokens(monkeypatch):
    fake = _FakeSupabase()
    monkeypatch.setattr(usage_repo, "get_supabase", lambda: fake)

    await usage.record(
        "u1", "groq", "chat", Usage(requests=1), est_input_tokens=200, est_output_tokens=40
    )

    params = fake.rpc_calls[0][1]
    assert (params["p_input"], params["p_output"]) == (200, 40)
    assert params["p_requests"] == 1  # the request count -- what quotas enforce -- is exact


@pytest.mark.asyncio
async def test_counts_at_least_one_request_even_if_the_adapter_did_not(monkeypatch):
    fake = _FakeSupabase()
    monkeypatch.setattr(usage_repo, "get_supabase", lambda: fake)

    await usage.record("u1", "gemini", "embed", Usage())

    assert fake.rpc_calls[0][1]["p_requests"] == 1


@pytest.mark.asyncio
async def test_a_bookkeeping_failure_never_breaks_the_users_request(monkeypatch):
    monkeypatch.setattr(usage_repo, "get_supabase", lambda: _FakeSupabase(error=RuntimeError("db down")))

    await usage.record("u1", "gemini", "chat", Usage(requests=1))  # must not raise


@pytest.mark.asyncio
async def test_usage_today_filters_by_user_and_day(monkeypatch):
    from app.llm import router

    seen = {}

    class _Q:
        def select(self, *a):
            return self

        def eq(self, field, value):
            seen[field] = value
            return self

        def execute(self):
            class R:
                data = [{"provider": "gemini", "kind": "chat", "requests": 3}]

            return R()

    class _DB:
        def table(self, name):
            seen["table"] = name
            return _Q()

    monkeypatch.setattr(usage_repo, "get_supabase", lambda: _DB())

    rows = await router.usage_today("u1")

    assert rows[0]["requests"] == 3
    assert seen["table"] == "llm_usage" and seen["user_id"] == "u1" and "day" in seen
