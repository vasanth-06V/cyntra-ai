"""Gateway behaviour added in M2: retry hints, cooldowns, timeouts, error
taxonomy, truncation, empty replies, deadlines, stream accounting, priority
lanes, structured logs."""

import asyncio
import json
import logging

import pytest
from fastapi import HTTPException

from app.core.jsonlog import JsonFormatter
from app.llm import gateway
from app.llm.keystate import cooldowns, key_hash
from app.llm.limiter import RateLimiter
from app.llm.options import LLMOptions
from app.providers.base import (
    Message,
    MessageRole,
    ProviderBadRequestError,
    ProviderConfigError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

from tests.test_gateway import USER, env  # noqa: F401  (fixture reuse)

MESSAGES = [Message(MessageRole.USER, "hello there")]


class Scripted:
    """chat() outcomes per call, in order: an exception to raise, or
    (text, finish_reason). Records every call."""

    def __init__(self, *outcomes, stream_chunks=None):
        self.outcomes = list(outcomes)
        self.calls: list[tuple[str, LLMOptions]] = []
        self.stream_chunks = stream_chunks

    async def chat(self, api_key, messages, stream=True, options=None, usage=None):
        self.calls.append((api_key, options))
        outcome = self.outcomes.pop(0) if self.outcomes else ("ok", "stop")
        if isinstance(outcome, Exception):
            raise outcome
        text, finish = outcome
        if usage is not None:
            usage.requests += 1
            usage.finish_reason = finish
            usage.model = "test-model"
        if stream and self.stream_chunks is not None:
            for c in self.stream_chunks:
                yield c
            if self.outcomes and isinstance(self.outcomes[0], Exception):
                raise self.outcomes.pop(0)
            return
        yield text


@pytest.fixture
def sleeps(monkeypatch):
    recorded: list[float] = []

    async def fake_sleep(seconds):
        recorded.append(seconds)

    monkeypatch.setattr(gateway.asyncio, "sleep", fake_sleep)
    return recorded


def use(env, monkeypatch, adapter):  # noqa: F811
    monkeypatch.setattr(gateway, "get_adapter", lambda provider: adapter)
    return adapter


# --- retry hints, rate-limit kinds, cooldowns --------------------------------


@pytest.mark.asyncio
async def test_a_provider_retry_after_hint_lengthens_the_backoff(env, monkeypatch, sleeps):  # noqa: F811
    monkeypatch.setattr(gateway, "_RETRY_DELAYS", (1.0, 2.0))
    adapter = use(env, monkeypatch, Scripted(ProviderUnavailableError("busy", retry_after=6.0), ("done", "stop")))

    assert await gateway.complete(USER, "gemini", MESSAGES) == "done"

    assert len(adapter.calls) == 2
    assert 3.0 <= sleeps[0] <= 6.0  # the hint (jittered), not the 1 s base


@pytest.mark.asyncio
async def test_a_short_per_minute_limit_is_waited_out_on_the_same_key(env, monkeypatch, sleeps):  # noqa: F811
    adapter = use(env, monkeypatch, Scripted(ProviderRateLimitError("slow down", kind="rpm", retry_after=3.0), ("done", "stop")))

    assert await gateway.complete(USER, "gemini", MESSAGES) == "done"

    assert [k for k, _ in adapter.calls] == ["primary-key", "primary-key"]  # no failover
    assert 3.0 in sleeps
    assert env.notified == []
    assert cooldowns.remaining("gemini", key_hash("primary-key")) == 0  # recovered, so not benched


@pytest.mark.asyncio
async def test_a_daily_quota_fails_over_at_once_and_benches_the_spent_key(env, monkeypatch, sleeps):  # noqa: F811
    adapter = use(env, monkeypatch, Scripted(ProviderRateLimitError("daily", kind="rpd")))

    await gateway.complete(USER, "gemini", MESSAGES)
    await gateway.complete(USER, "gemini", MESSAGES)

    # The second call never touched the spent primary key.
    assert [k for k, _ in adapter.calls] == ["primary-key", "backup-key", "backup-key"]
    assert cooldowns.remaining("gemini", key_hash("primary-key")) > 3600  # until Pacific midnight


@pytest.mark.asyncio
async def test_when_every_key_is_benched_the_user_gets_a_clear_429(env, monkeypatch, sleeps):  # noqa: F811
    use(env, monkeypatch, Scripted())
    cooldowns.set("gemini", key_hash("primary-key"), 7200)
    cooldowns.set("gemini", key_hash("backup-key"), 7200)

    with pytest.raises(HTTPException) as exc:
        await gateway.complete(USER, "gemini", MESSAGES)

    assert exc.value.status_code == 429 and exc.value.code == "quota_exhausted"
    assert "2 min" not in exc.value.detail and "min" in exc.value.detail  # tells them roughly when


@pytest.mark.asyncio
async def test_each_key_gets_its_own_limiter_budget(env, monkeypatch):  # noqa: F811
    use(env, monkeypatch, Scripted(ProviderRateLimitError("q")))
    await gateway.complete(USER, "gemini", MESSAGES)
    owners = [owner for owner, _ in env.limiter.acquired]
    assert owners == [key_hash("primary-key"), key_hash("backup-key")]  # the backup is not throttled by the primary


# --- timeouts and the error taxonomy --------------------------------------------


@pytest.mark.asyncio
async def test_a_timed_out_call_is_retried_once_then_reported_as_504(env, monkeypatch, sleeps):  # noqa: F811
    adapter = use(env, monkeypatch, Scripted(*[ProviderTimeoutError("slow")] * 5))

    with pytest.raises(HTTPException) as exc:
        await gateway.complete(USER, "gemini", MESSAGES)

    assert exc.value.status_code == 504 and exc.value.code == "provider_timeout"
    assert len(adapter.calls) == 2


@pytest.mark.asyncio
async def test_a_bad_request_is_our_problem_not_the_users_key_and_is_not_retried(env, monkeypatch):  # noqa: F811
    adapter = use(env, monkeypatch, Scripted(ProviderBadRequestError("prompt too long")))

    with pytest.raises(HTTPException) as exc:
        await gateway.complete(USER, "gemini", MESSAGES)

    assert exc.value.status_code == 502 and exc.value.code == "provider_bad_request"
    assert "key" not in exc.value.detail.lower()
    assert len(adapter.calls) == 1


@pytest.mark.asyncio
async def test_a_retired_model_is_a_loud_non_retried_config_error(env, monkeypatch):  # noqa: F811
    adapter = use(env, monkeypatch, Scripted(ProviderConfigError("model not found")))

    with pytest.raises(HTTPException) as exc:
        await gateway.complete(USER, "gemini", MESSAGES)

    assert exc.value.status_code == 503 and exc.value.code == "provider_misconfigured"
    assert len(adapter.calls) == 1


@pytest.mark.asyncio
async def test_a_configured_fallback_model_is_tried_when_the_first_is_retired(env, monkeypatch):  # noqa: F811
    monkeypatch.setitem(gateway.FALLBACKS, "gemini", {"chat": ["backup-model"]})
    adapter = use(env, monkeypatch, Scripted(ProviderConfigError("model not found"), ("from fallback", "stop")))

    assert await gateway.complete(USER, "gemini", MESSAGES) == "from fallback"
    assert [o.model_override for _, o in adapter.calls] == [None, "backup-model"]


@pytest.mark.asyncio
async def test_a_call_that_never_returns_is_cut_off_by_the_overall_deadline(env, monkeypatch):  # noqa: F811
    class Hangs:
        async def chat(self, *a, **k):
            await asyncio.sleep(30)
            yield "never"

    use(env, monkeypatch, Hangs())
    monkeypatch.setattr(gateway, "_DEADLINE_SLACK", 0.0)

    with pytest.raises(HTTPException) as exc:
        await gateway.complete(USER, "gemini", MESSAGES, LLMOptions(timeout_s=0.02))

    assert exc.value.status_code == 504


# --- finish reasons --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_truncated_reply_is_trimmed_to_a_whole_sentence_when_asked(env, monkeypatch):  # noqa: F811
    cut = "First point is clear. Second point is clear too. And the third sen"
    use(env, monkeypatch, Scripted((cut, "length"), (cut, "length")))

    trimmed = await gateway.complete_full(USER, "gemini", MESSAGES, LLMOptions(trim_on_length=True))
    raw = await gateway.complete_full(USER, "gemini", MESSAGES, LLMOptions())

    assert trimmed.text == "First point is clear. Second point is clear too."
    assert trimmed.truncated and trimmed.finish_reason == "length"
    assert raw.text == cut  # untouched unless the caller opts in


@pytest.mark.asyncio
async def test_an_empty_reply_caused_by_a_spent_token_budget_is_retried_with_more_room(env, monkeypatch):  # noqa: F811
    adapter = use(env, monkeypatch, Scripted(("", "length"), ("Now with room to answer.", "stop")))

    result = await gateway.complete_full(USER, "gemini", MESSAGES, LLMOptions(max_output_tokens=100))

    assert result.text == "Now with room to answer."
    assert [o.max_output_tokens for _, o in adapter.calls] == [100, 200]


@pytest.mark.asyncio
async def test_an_empty_reply_that_stays_empty_is_a_clean_error_not_a_blank_message(env, monkeypatch):  # noqa: F811
    use(env, monkeypatch, Scripted(("", "stop")))

    with pytest.raises(HTTPException) as exc:
        await gateway.complete(USER, "gemini", MESSAGES, LLMOptions(max_output_tokens=100))

    assert exc.value.status_code == 502 and exc.value.code == "empty_reply"


# --- streaming accounting ------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_usage_is_recorded_when_the_consumer_disconnects_mid_stream(env, monkeypatch):  # noqa: F811
    use(env, monkeypatch, Scripted(("", "stop"), stream_chunks=["Hel", "lo ", "world"]))

    agen = gateway.stream(USER, "gemini", MESSAGES)
    assert await agen.__anext__() == "Hel"
    await agen.aclose()  # the client went away

    assert len(env.recorded) == 1  # the provider still counted that request
    assert env.recorded[0]["est_out"] >= 1


@pytest.mark.asyncio
async def test_usage_is_recorded_when_the_stream_breaks_after_output(env, monkeypatch):  # noqa: F811
    use(env, monkeypatch, Scripted(("", "stop"), ProviderUnavailableError("dropped"), stream_chunks=["partial"]))

    with pytest.raises(ProviderUnavailableError):
        async for _ in gateway.stream(USER, "gemini", MESSAGES):
            pass

    assert len(env.recorded) == 1


@pytest.mark.asyncio
async def test_a_stream_that_failed_before_any_output_records_no_usage(env, monkeypatch):  # noqa: F811
    use(env, monkeypatch, Scripted(*[ProviderBadRequestError("no")] * 3))

    with pytest.raises(HTTPException):
        async for _ in gateway.stream(USER, "gemini", MESSAGES):
            pass

    assert env.recorded == []


# --- limiter priority lanes -------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_background_work_cannot_use_the_last_quarter_of_the_window():
    now = [0.0]
    waited: list[float] = []

    async def fake_sleep(seconds):
        waited.append(seconds)
        now[0] += seconds

    limiter = RateLimiter(limits={"gemini": 8}, clock=lambda: now[0], sleep=fake_sleep, max_wait=120)
    for _ in range(6):
        await limiter.acquire("key", "gemini", "background")
    assert waited == []

    await limiter.acquire("key", "gemini", "interactive")  # a live turn goes straight through
    assert waited == []

    await limiter.acquire("key", "gemini", "background")  # the 7th background call has to wait
    assert waited and waited[0] > 0


# --- structured call logs --------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_every_call_writes_one_structured_log_line_without_prompts_or_keys(env, monkeypatch):  # noqa: F811
    use(env, monkeypatch, Scripted(("secret answer text", "stop")))
    lines: list[str] = []

    class Capture(logging.Handler):
        def emit(self, record):
            lines.append(self.format(record))

    handler = Capture()
    handler.setFormatter(JsonFormatter())
    log = logging.getLogger("app.llm")
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    try:
        await gateway.complete(
            USER,
            "gemini",
            [Message(MessageRole.USER, "my private prompt")],
            LLMOptions(task="interview", feature="interview_turn", prompt_id="interview.turn", prompt_version="1"),
        )
    finally:
        log.removeHandler(handler)

    entry = json.loads(next(line for line in lines if '"llm_call"' in line))
    assert entry["feature"] == "interview_turn" and entry["task"] == "interview"
    assert entry["provider"] == "gemini" and entry["outcome"] == "ok" and entry["finish_reason"] == "stop"
    assert entry["prompt_id"] == "interview.turn" and entry["key_slot"] == "primary"
    assert "latency_ms" in entry
    joined = "\n".join(lines)
    assert "my private prompt" not in joined and "secret answer text" not in joined
    assert "primary-key" not in joined  # keys never reach the logs


@pytest.mark.asyncio
async def test_embed_passes_the_kind_through(env, monkeypatch):  # noqa: F811
    kinds: list[str] = []

    async def fake_embed_texts(api_key, texts, usage=None, kind="doc"):
        kinds.append(kind)
        return [[0.0] for _ in texts]

    monkeypatch.setattr(gateway, "embed_texts", fake_embed_texts)
    await gateway.embed(USER, ["a"], kind="query")
    await gateway.embed(USER, ["a"])
    assert kinds == ["query", "doc"]
