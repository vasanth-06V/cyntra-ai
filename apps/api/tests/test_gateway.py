import pytest
from fastapi import HTTPException

from app.llm import gateway
from app.llm.options import LLMOptions, Usage
from app.providers.base import (
    Message,
    MessageRole,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderUnavailableError,
)

USER = "user-1"
MESSAGES = [Message(MessageRole.USER, "hello there")]


class FakeAdapter:
    """Scripted per API key. An outcome is "ok", an exception raised before
    any output, or ("mid", exc): emit one chunk, then fail."""

    def __init__(self, outcomes: dict[str, list] | None = None):
        self.outcomes = outcomes or {}
        self.calls: list[str] = []
        self.last_options: LLMOptions | None = None
        self.last_stream: bool | None = None

    async def chat(self, api_key, messages, stream=True, options=None, usage=None):
        self.calls.append(api_key)
        self.last_options, self.last_stream = options, stream
        script = self.outcomes.get(api_key, [])
        outcome = script.pop(0) if script else "ok"

        if isinstance(outcome, Exception):
            raise outcome
        if isinstance(outcome, tuple):
            yield "part"
            raise outcome[1]

        if usage is not None:
            usage.requests += 1
            usage.input_tokens += 10
            usage.output_tokens += 5
        for chunk in ("Hello", ", ", "world"):
            yield chunk


class FakeLimiter:
    def __init__(self):
        self.acquired: list[tuple[str, str]] = []

    async def acquire(self, user_id, bucket):
        self.acquired.append((user_id, bucket))


@pytest.fixture
def env(monkeypatch):
    class Env:
        keys = {"primary": "primary-key", "backup": "backup-key"}
        adapter = FakeAdapter()
        limiter = FakeLimiter()
        notified: list[str] = []
        recorded: list[dict] = []

    e = Env()
    e.notified, e.recorded = [], []

    async def fake_get_key_row(user_id, provider, slot):
        key = e.keys.get(slot)
        return {"id": slot, "encrypted_key": key} if key else None

    async def fake_notify(user_id, message):
        e.notified.append(message)

    async def fake_record(user_id, provider, kind, usage, est_input_tokens=0, est_output_tokens=0):
        e.recorded.append(
            {"provider": provider, "kind": kind, "usage": usage, "est_in": est_input_tokens, "est_out": est_output_tokens}
        )

    monkeypatch.setattr(gateway, "get_adapter", lambda provider: e.adapter)
    monkeypatch.setattr(gateway, "get_key_row", fake_get_key_row)
    monkeypatch.setattr(gateway, "decrypt_key", lambda encrypted: encrypted)
    monkeypatch.setattr(gateway, "notify_user", fake_notify)
    monkeypatch.setattr(gateway.usage_log, "record", fake_record)
    monkeypatch.setattr(gateway, "limiter", e.limiter)
    monkeypatch.setattr(gateway, "_RETRY_DELAYS", (0, 0))
    return e


async def _collect(agen) -> str:
    return "".join([c async for c in agen])


# --- complete ---


@pytest.mark.asyncio
async def test_complete_uses_the_primary_key_passes_options_and_records_usage(env):
    options = LLMOptions(task="extract", json_mode=True, max_output_tokens=50)

    text = await gateway.complete(USER, "gemini", MESSAGES, options)

    assert text == "Hello, world"
    assert env.adapter.calls == ["primary-key"]
    assert env.adapter.last_options == options
    assert env.adapter.last_stream is False
    assert env.limiter.acquired == [(USER, "gemini")]
    assert env.recorded[0]["kind"] == "chat"
    assert env.recorded[0]["usage"] == Usage(requests=1, input_tokens=10, output_tokens=5)
    assert env.recorded[0]["est_in"] > 0  # fallback estimate is supplied too


@pytest.mark.asyncio
async def test_complete_fails_over_to_the_backup_key_and_notifies(env):
    env.adapter.outcomes = {"primary-key": [ProviderRateLimitError("quota")]}

    text = await gateway.complete(USER, "gemini", MESSAGES)

    assert text == "Hello, world"
    assert env.adapter.calls == ["primary-key", "backup-key"]
    assert "switched to your backup key" in env.notified[0]


@pytest.mark.asyncio
async def test_complete_429_when_rate_limited_and_no_backup(env):
    env.keys = {"primary": "primary-key"}
    env.adapter.outcomes = {"primary-key": [ProviderRateLimitError("quota")]}

    with pytest.raises(HTTPException) as exc:
        await gateway.complete(USER, "gemini", MESSAGES)

    assert exc.value.status_code == 429
    assert "no backup key" in exc.value.detail
    assert env.notified == []


@pytest.mark.asyncio
async def test_complete_429_when_both_keys_are_rate_limited_and_nobody_is_notified(env):
    env.adapter.outcomes = {
        "primary-key": [ProviderRateLimitError("q")],
        "backup-key": [ProviderRateLimitError("q")],
    }

    with pytest.raises(HTTPException) as exc:
        await gateway.complete(USER, "gemini", MESSAGES)

    assert exc.value.status_code == 429
    assert "Both primary and backup" in exc.value.detail
    assert env.notified == []


@pytest.mark.asyncio
async def test_complete_412_when_no_key_is_configured(env):
    env.keys = {}

    with pytest.raises(HTTPException) as exc:
        await gateway.complete(USER, "gemini", MESSAGES)

    assert exc.value.status_code == 412
    assert env.adapter.calls == []


@pytest.mark.asyncio
async def test_complete_retries_a_transient_outage_then_succeeds(env):
    env.adapter.outcomes = {
        "primary-key": [ProviderUnavailableError("busy"), ProviderUnavailableError("busy")]
    }

    text = await gateway.complete(USER, "gemini", MESSAGES)

    assert text == "Hello, world"
    assert env.adapter.calls == ["primary-key"] * 3
    assert len(env.limiter.acquired) == 3  # every attempt goes through the limiter


@pytest.mark.asyncio
async def test_complete_503_when_the_provider_stays_overloaded(env):
    env.adapter.outcomes = {"primary-key": [ProviderUnavailableError("busy")] * 10}

    with pytest.raises(HTTPException) as exc:
        await gateway.complete(USER, "gemini", MESSAGES)

    assert exc.value.status_code == 503
    assert "try again" in exc.value.detail
    assert env.adapter.calls == ["primary-key"] * 3  # one attempt + two retries


@pytest.mark.asyncio
async def test_complete_400_when_the_provider_rejects_the_key(env):
    env.adapter.outcomes = {"primary-key": [ProviderAuthError("revoked")]}

    with pytest.raises(HTTPException) as exc:
        await gateway.complete(USER, "gemini", MESSAGES)

    assert exc.value.status_code == 400
    assert "Settings" in exc.value.detail


@pytest.mark.asyncio
async def test_backup_key_is_also_retried_on_transient_errors(env):
    env.adapter.outcomes = {
        "primary-key": [ProviderRateLimitError("q")],
        "backup-key": [ProviderUnavailableError("busy")],
    }

    text = await gateway.complete(USER, "gemini", MESSAGES)

    assert text == "Hello, world"
    assert env.adapter.calls == ["primary-key", "backup-key", "backup-key"]


# --- stream ---


@pytest.mark.asyncio
async def test_stream_yields_chunks_in_order_and_records_usage_once(env):
    text = await _collect(gateway.stream(USER, "gemini", MESSAGES))

    assert text == "Hello, world"
    assert env.adapter.last_stream is True
    assert len(env.recorded) == 1 and env.recorded[0]["kind"] == "chat"


@pytest.mark.asyncio
async def test_stream_retries_before_the_first_chunk(env):
    env.adapter.outcomes = {"primary-key": [ProviderUnavailableError("busy")]}

    text = await _collect(gateway.stream(USER, "gemini", MESSAGES))

    assert text == "Hello, world"
    assert env.adapter.calls == ["primary-key", "primary-key"]


@pytest.mark.asyncio
async def test_stream_does_not_retry_after_output_started(env):
    env.adapter.outcomes = {"primary-key": [("mid", ProviderUnavailableError("dropped"))]}
    received = []

    with pytest.raises(ProviderUnavailableError):
        async for chunk in gateway.stream(USER, "gemini", MESSAGES):
            received.append(chunk)

    assert received == ["part"]
    assert env.adapter.calls == ["primary-key"]  # retrying would repeat "part"


@pytest.mark.asyncio
async def test_stream_does_not_fail_over_after_output_started(env):
    env.adapter.outcomes = {"primary-key": [("mid", ProviderRateLimitError("quota"))]}

    with pytest.raises(ProviderRateLimitError):
        await _collect(gateway.stream(USER, "gemini", MESSAGES))

    assert env.adapter.calls == ["primary-key"]
    assert env.notified == []


@pytest.mark.asyncio
async def test_stream_fails_over_to_the_backup_before_any_output(env):
    env.adapter.outcomes = {"primary-key": [ProviderRateLimitError("quota")]}

    text = await _collect(gateway.stream(USER, "gemini", MESSAGES))

    assert text == "Hello, world"
    assert env.adapter.calls == ["primary-key", "backup-key"]
    assert "switched to your backup key" in env.notified[0]


@pytest.mark.asyncio
async def test_stream_503_when_still_overloaded_before_any_output(env):
    env.adapter.outcomes = {"primary-key": [ProviderUnavailableError("busy")] * 10}

    with pytest.raises(HTTPException) as exc:
        await _collect(gateway.stream(USER, "gemini", MESSAGES))

    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_stream_412_without_a_key(env):
    env.keys = {}

    with pytest.raises(HTTPException) as exc:
        await _collect(gateway.stream(USER, "gemini", MESSAGES))

    assert exc.value.status_code == 412


# --- embed ---


@pytest.fixture
def embed_env(env, monkeypatch):
    calls: list[tuple[str, list[str]]] = []
    outcomes: dict[str, list] = {}

    async def fake_embed_texts(api_key, texts, usage=None):
        calls.append((api_key, list(texts)))
        script = outcomes.get(api_key, [])
        if script:
            raise script.pop(0)
        if usage is not None:
            usage.requests += 1
        return [[0.0] for _ in texts]

    monkeypatch.setattr(gateway, "embed_texts", fake_embed_texts)
    env.embed_calls, env.embed_outcomes = calls, outcomes
    return env


@pytest.mark.asyncio
async def test_embed_sends_one_batch_through_the_gemini_embed_bucket(embed_env):
    vectors = await gateway.embed(USER, ["a", "b", "c"])

    assert len(vectors) == 3
    assert embed_env.embed_calls == [("primary-key", ["a", "b", "c"])]
    assert embed_env.limiter.acquired == [(USER, "gemini:embed")]
    assert embed_env.recorded[0]["provider"] == "gemini"
    assert embed_env.recorded[0]["kind"] == "embed"


@pytest.mark.asyncio
async def test_embed_now_fails_over_to_the_backup_key_too(embed_env):
    embed_env.embed_outcomes["primary-key"] = [ProviderRateLimitError("quota")]

    await gateway.embed(USER, ["a"])

    assert [k for k, _ in embed_env.embed_calls] == ["primary-key", "backup-key"]
    assert "switched to your backup key" in embed_env.notified[0]


@pytest.mark.asyncio
async def test_embed_412_without_a_gemini_key(embed_env):
    embed_env.keys = {}

    with pytest.raises(HTTPException) as exc:
        await gateway.embed(USER, ["a"])

    assert exc.value.status_code == 412
