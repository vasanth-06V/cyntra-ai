import pytest

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
    monkeypatch.setattr(usage, "get_supabase", lambda: fake)

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
    monkeypatch.setattr(usage, "get_supabase", lambda: fake)

    await usage.record(
        "u1", "groq", "chat", Usage(requests=1), est_input_tokens=200, est_output_tokens=40
    )

    params = fake.rpc_calls[0][1]
    assert (params["p_input"], params["p_output"]) == (200, 40)
    assert params["p_requests"] == 1  # the request count -- what quotas enforce -- is exact


@pytest.mark.asyncio
async def test_counts_at_least_one_request_even_if_the_adapter_did_not(monkeypatch):
    fake = _FakeSupabase()
    monkeypatch.setattr(usage, "get_supabase", lambda: fake)

    await usage.record("u1", "gemini", "embed", Usage())

    assert fake.rpc_calls[0][1]["p_requests"] == 1


@pytest.mark.asyncio
async def test_a_bookkeeping_failure_never_breaks_the_users_request(monkeypatch):
    monkeypatch.setattr(usage, "get_supabase", lambda: _FakeSupabase(error=RuntimeError("db down")))

    await usage.record("u1", "gemini", "chat", Usage(requests=1))  # must not raise
