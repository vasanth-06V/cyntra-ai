"""Claude and Groq adapters through their real SDKs, with the HTTP layer
scripted (no network, no keys). Covers response parsing, finish reasons,
usage, SDK-retry suppression and the error taxonomy."""

import json

import httpx
import pytest
from anthropic import AsyncAnthropic
from groq import AsyncGroq

from app.llm.options import LLMOptions, Usage
from app.providers import claude, groq
from app.providers.base import (
    Message,
    MessageRole,
    ProviderAuthError,
    ProviderBadRequestError,
    ProviderBlockedError,
    ProviderConfigError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

USER = [Message(MessageRole.USER, "hello")]


async def collect(agen) -> str:
    return "".join([c async for c in agen])


class Net:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.requests: list[httpx.Request] = []

    def handler(self, request):
        self.requests.append(request)
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(reply, Exception):
            raise reply
        return reply

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handler))


def sse(events: list[tuple[str, dict]]) -> httpx.Response:
    body = "".join(f"event: {name}\ndata: {json.dumps(data)}\n\n" for name, data in events)
    return httpx.Response(200, content=body.encode(), headers={"content-type": "text/event-stream"})


# ----------------------------------------------------------------- Claude


def claude_adapter(net: Net, monkeypatch) -> claude.ClaudeAdapter:
    monkeypatch.setattr(
        claude.ClaudeAdapter,
        "_client",
        staticmethod(lambda api_key, timeout: AsyncAnthropic(api_key=api_key, max_retries=0, http_client=net.client())),
    )
    return claude.ClaudeAdapter()


def claude_message(text="hi", stop="end_turn", **usage):
    return httpx.Response(
        200,
        json={
            "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-sonnet-5-5",
            "content": [{"type": "text", "text": text}],
            "stop_reason": stop, "stop_sequence": None,
            "usage": {"input_tokens": 11, "output_tokens": 4, **usage},
        },
    )


@pytest.mark.asyncio
async def test_claude_reply_usage_finish_reason_and_model(monkeypatch):
    net = Net(claude_message("Answer.", "max_tokens"))
    usage = Usage()
    text = await collect(claude_adapter(net, monkeypatch).chat("k", USER, stream=False, usage=usage))
    assert text == "Answer."
    assert (usage.requests, usage.input_tokens, usage.output_tokens) == (1, 11, 4)
    assert usage.finish_reason == "length" and usage.model == "claude-sonnet-5-5"


@pytest.mark.asyncio
async def test_claude_short_caps_are_raised_so_adaptive_reasoning_cannot_leave_an_empty_reply(monkeypatch):
    net = Net(claude_message())
    await collect(claude_adapter(net, monkeypatch).chat("k", USER, stream=False, options=LLMOptions(max_output_tokens=150)))
    assert json.loads(net.requests[0].content)["max_tokens"] >= 1024


@pytest.mark.asyncio
async def test_claude_system_messages_are_joined(monkeypatch):
    net = Net(claude_message())
    messages = [Message(MessageRole.SYSTEM, "one"), Message(MessageRole.SYSTEM, "two"), *USER]
    await collect(claude_adapter(net, monkeypatch).chat("k", messages, stream=False))
    assert json.loads(net.requests[0].content)["system"] == "one\n\ntwo"


@pytest.mark.asyncio
async def test_claude_refusal_with_no_text_is_a_blocked_reply(monkeypatch):
    net = Net(httpx.Response(200, json={
        "id": "m", "type": "message", "role": "assistant", "model": "x", "content": [],
        "stop_reason": "refusal", "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 0},
    }))
    with pytest.raises(ProviderBlockedError):
        await collect(claude_adapter(net, monkeypatch).chat("k", USER, stream=False))


@pytest.mark.asyncio
async def test_claude_streaming_reports_text_ttft_and_final_usage(monkeypatch):
    events = [
        ("message_start", {"type": "message_start", "message": {"id": "m", "type": "message", "role": "assistant", "model": "x", "content": [], "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 5, "output_tokens": 1}}}),
        ("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}),
        ("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Hel"}}),
        ("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "lo"}}),
        ("content_block_stop", {"type": "content_block_stop", "index": 0}),
        ("message_delta", {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None}, "usage": {"output_tokens": 7}}),
        ("message_stop", {"type": "message_stop"}),
    ]
    usage = Usage()
    pieces = [c async for c in claude_adapter(Net(sse(events)), monkeypatch).chat("k", USER, stream=True, usage=usage)]
    assert pieces == ["Hel", "lo"]
    assert usage.finish_reason == "stop" and usage.output_tokens == 7 and usage.ttft_ms is not None


@pytest.mark.parametrize(
    "response,expected",
    [
        (httpx.Response(429, json={"type": "error", "error": {"type": "rate_limit_error", "message": "slow"}}, headers={"retry-after": "9"}), ProviderRateLimitError),
        (httpx.Response(401, json={"type": "error", "error": {"type": "authentication_error", "message": "bad key"}}), ProviderAuthError),
        (httpx.Response(403, json={"type": "error", "error": {"type": "permission_error", "message": "no"}}), ProviderAuthError),
        (httpx.Response(404, json={"type": "error", "error": {"type": "not_found_error", "message": "model: x"}}), ProviderConfigError),
        (httpx.Response(400, json={"type": "error", "error": {"type": "invalid_request_error", "message": "too long"}}), ProviderBadRequestError),
        (httpx.Response(500, json={"type": "error", "error": {"type": "api_error", "message": "oops"}}), ProviderUnavailableError),
        (httpx.Response(529, json={"type": "error", "error": {"type": "overloaded_error", "message": "busy"}}), ProviderUnavailableError),
    ],
)
@pytest.mark.asyncio
async def test_claude_errors_map_to_typed_errors(monkeypatch, response, expected):
    adapter = claude_adapter(Net(response), monkeypatch)
    with pytest.raises(expected):
        await collect(adapter.chat("k", USER, stream=False))


@pytest.mark.asyncio
async def test_claude_rate_limit_carries_the_retry_after_hint_and_the_sdk_does_not_retry_itself(monkeypatch):
    net = Net(httpx.Response(429, json={"type": "error", "error": {"type": "rate_limit_error", "message": "slow"}}, headers={"retry-after": "9"}))
    with pytest.raises(ProviderRateLimitError) as exc:
        await collect(claude_adapter(net, monkeypatch).chat("k", USER, stream=False))
    assert exc.value.retry_after == 9.0
    assert len(net.requests) == 1  # max_retries=0: the gateway is the only retry layer


@pytest.mark.asyncio
async def test_claude_timeouts_and_connection_errors(monkeypatch):
    with pytest.raises(ProviderTimeoutError):
        await collect(claude_adapter(Net(httpx.ReadTimeout("slow")), monkeypatch).chat("k", USER, stream=False))
    with pytest.raises(ProviderUnavailableError):
        await collect(claude_adapter(Net(httpx.ConnectError("refused")), monkeypatch).chat("k", USER, stream=False))


@pytest.mark.asyncio
async def test_claude_validate_false_for_a_bad_key_and_typed_errors_otherwise(monkeypatch):
    bad = Net(httpx.Response(401, json={"type": "error", "error": {"type": "authentication_error", "message": "bad"}}))
    assert await claude_adapter(bad, monkeypatch).validate("k") is False
    limited = Net(httpx.Response(429, json={"type": "error", "error": {"type": "rate_limit_error", "message": "slow"}}))
    with pytest.raises(ProviderRateLimitError):
        await claude_adapter(limited, monkeypatch).validate("k")


# ------------------------------------------------------------------- Groq


def groq_adapter(net: Net, monkeypatch) -> groq.GroqAdapter:
    monkeypatch.setattr(
        groq.GroqAdapter,
        "_client",
        staticmethod(lambda api_key, timeout: AsyncGroq(api_key=api_key, max_retries=0, http_client=net.client())),
    )
    return groq.GroqAdapter()


def groq_completion(text="hi", finish="stop"):
    return httpx.Response(
        200,
        json={
            "id": "c1", "object": "chat.completion", "created": 1, "model": "llama-3.3-70b-versatile",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": finish}],
            "usage": {"prompt_tokens": 8, "completion_tokens": 3, "total_tokens": 11},
        },
    )


@pytest.mark.asyncio
async def test_groq_reply_usage_and_finish_reason(monkeypatch):
    usage = Usage()
    text = await collect(groq_adapter(Net(groq_completion("Done.", "length")), monkeypatch).chat("k", USER, stream=False, usage=usage))
    assert text == "Done."
    assert (usage.requests, usage.input_tokens, usage.output_tokens) == (1, 8, 3)
    assert usage.finish_reason == "length" and usage.model == "llama-3.3-70b-versatile"


@pytest.mark.asyncio
async def test_groq_json_mode_and_caps_are_sent(monkeypatch):
    net = Net(groq_completion('{"a": 1}'))
    options = LLMOptions(task="extract", json_mode=True, max_output_tokens=50, temperature=0.0)
    await collect(groq_adapter(net, monkeypatch).chat("k", USER, stream=False, options=options))
    body = json.loads(net.requests[0].content)
    assert body["response_format"] == {"type": "json_object"}
    assert body["max_tokens"] == 50 and body["temperature"] == 0.0
    assert body["model"] == "llama-3.1-8b-instant"


@pytest.mark.asyncio
async def test_groq_streaming_yields_text_and_finish_reason(monkeypatch):
    def chunk(delta, finish=None):
        return {"id": "c", "object": "chat.completion.chunk", "created": 1, "model": "m",
                "choices": [{"index": 0, "delta": {"content": delta}, "finish_reason": finish}]}

    body = "".join(f"data: {json.dumps(c)}\n\n" for c in [chunk("Hel"), chunk("lo"), chunk(None, "stop")]) + "data: [DONE]\n\n"
    net = Net(httpx.Response(200, content=body.encode(), headers={"content-type": "text/event-stream"}))
    usage = Usage()
    pieces = [c async for c in groq_adapter(net, monkeypatch).chat("k", USER, stream=True, usage=usage)]
    assert pieces == ["Hel", "lo"]
    assert usage.finish_reason == "stop" and usage.requests == 1 and usage.ttft_ms is not None


@pytest.mark.parametrize(
    "response,expected",
    [
        (httpx.Response(429, json={"error": {"message": "rate limit", "type": "tokens"}}, headers={"retry-after": "4"}), ProviderRateLimitError),
        (httpx.Response(401, json={"error": {"message": "invalid api key"}}), ProviderAuthError),
        (httpx.Response(403, json={"error": {"message": "forbidden"}}), ProviderAuthError),
        (httpx.Response(404, json={"error": {"message": "model not found"}}), ProviderConfigError),
        (httpx.Response(400, json={"error": {"message": "json_validate_failed"}}), ProviderBadRequestError),
        (httpx.Response(503, json={"error": {"message": "over capacity"}}), ProviderUnavailableError),
    ],
)
@pytest.mark.asyncio
async def test_groq_errors_map_to_typed_errors(monkeypatch, response, expected):
    with pytest.raises(expected):
        await collect(groq_adapter(Net(response), monkeypatch).chat("k", USER, stream=False))


@pytest.mark.asyncio
async def test_groq_rate_limit_hint_and_no_sdk_retries(monkeypatch):
    net = Net(httpx.Response(429, json={"error": {"message": "rate limit"}}, headers={"retry-after": "4"}))
    with pytest.raises(ProviderRateLimitError) as exc:
        await collect(groq_adapter(net, monkeypatch).chat("k", USER, stream=False))
    assert exc.value.retry_after == 4.0 and len(net.requests) == 1


@pytest.mark.asyncio
async def test_groq_timeout_maps_to_a_typed_error(monkeypatch):
    with pytest.raises(ProviderTimeoutError):
        await collect(groq_adapter(Net(httpx.ReadTimeout("slow")), monkeypatch).chat("k", USER, stream=False))
