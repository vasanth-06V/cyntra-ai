"""The real GeminiAdapter against scripted HTTP responses (httpx.MockTransport):
request bodies, headers, SSE parsing, error mapping, thinking self-heal,
embeddings. No SDK, no network."""

import json
import math

import httpx
import pytest

from app.llm.models import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL
from app.llm.options import LLMOptions, Usage
from app.providers import gemini
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
from app.providers.gemini import GeminiAdapter, map_error

USER = [Message(MessageRole.USER, "hello")]


@pytest.fixture(autouse=True)
def _forget_thinking_rejections():
    gemini._thinking_rejected.clear()
    yield
    gemini._thinking_rejected.clear()


class Net:
    """Records requests and replies from a queue (the last reply repeats)."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(reply, Exception):
            raise reply
        return reply

    def adapter(self) -> GeminiAdapter:
        return GeminiAdapter(transport=httpx.MockTransport(self.handler))

    def body(self, index=0) -> dict:
        return json.loads(self.requests[index].content)


def ok(text="hi", finish="STOP", usage=None, **extra):
    return httpx.Response(
        200,
        json={
            "candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": finish}],
            "usageMetadata": usage or {"promptTokenCount": 12, "candidatesTokenCount": 3, "thoughtsTokenCount": 7},
            **extra,
        },
    )


def google_error(status, message="boom", google_status="", details=None, headers=None):
    return httpx.Response(
        status,
        json={"error": {"code": status, "message": message, "status": google_status, "details": details or []}},
        headers=headers,
    )


async def collect(agen) -> str:
    return "".join([c async for c in agen])


def sse(*chunks) -> httpx.Response:
    body = "".join(f"data: {json.dumps(c)}\r\n\r\n" for c in chunks)
    return httpx.Response(200, content=body.encode(), headers={"content-type": "text/event-stream"})


def chunk(text="", finish=None, usage=None):
    c: dict = {"candidates": [{"content": {"parts": [{"text": text}] if text else []}}]}
    if finish:
        c["candidates"][0]["finishReason"] = finish
    if usage:
        c["usageMetadata"] = usage
    return c


# --- validate -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_lists_models_with_the_key_in_a_header_not_the_url():
    net = Net(httpx.Response(200, json={"models": []}))
    assert await net.adapter().validate("secret-key") is True
    request = net.requests[0]
    assert request.method == "GET" and request.url.path.endswith("/models")
    assert request.headers["x-goog-api-key"] == "secret-key"
    assert "secret-key" not in str(request.url)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 401, 403])
async def test_validate_false_when_google_rejects_the_key(status):
    net = Net(google_error(status, "API key not valid. Please pass a valid API key.", "INVALID_ARGUMENT"))
    assert await net.adapter().validate("bad") is False


@pytest.mark.asyncio
async def test_validate_distinguishes_rate_limit_and_outage_from_an_invalid_key():
    with pytest.raises(ProviderRateLimitError):
        await Net(google_error(429, "quota", "RESOURCE_EXHAUSTED")).adapter().validate("k")
    with pytest.raises(ProviderUnavailableError):
        await Net(google_error(503, "overloaded", "UNAVAILABLE")).adapter().validate("k")


# --- request shape ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_request_carries_system_instruction_generation_config_and_thinking_control():
    net = Net(ok("answer"))
    options = LLMOptions(task="interview", max_output_tokens=160, temperature=0.3, json_mode=True)
    messages = [
        Message(MessageRole.SYSTEM, "You are an interviewer."),
        Message(MessageRole.SYSTEM, "Summary so far."),
        Message(MessageRole.USER, "Hi"),
        Message(MessageRole.ASSISTANT, "Hello"),
        Message(MessageRole.USER, "Go on"),
    ]
    text = await collect(net.adapter().chat("k", messages, stream=False, options=options))
    assert text == "answer"

    body = net.body()
    assert body["systemInstruction"]["parts"][0]["text"] == "You are an interviewer.\n\nSummary so far."
    assert [c["role"] for c in body["contents"]] == ["user", "model", "user"]
    config = body["generationConfig"]
    # room for thinking is added on top of the caller's cap
    assert config["maxOutputTokens"] == 160 + gemini.gemini_traits("gemini-flash-lite-latest")["allowance"]
    assert config["temperature"] == 0.3 and config["responseMimeType"] == "application/json"
    assert config["thinkingConfig"] == {"thinkingLevel": "minimal"}
    assert net.requests[0].url.path.endswith("models/gemini-flash-lite-latest:generateContent")


@pytest.mark.asyncio
async def test_two_calls_with_different_keys_never_share_credentials():
    net = Net(ok("a"))
    adapter = net.adapter()
    await collect(adapter.chat("key-one", USER, stream=False))
    await collect(adapter.chat("key-two", USER, stream=False))
    assert [r.headers["x-goog-api-key"] for r in net.requests] == ["key-one", "key-two"]


@pytest.mark.asyncio
async def test_usage_finish_reason_model_and_thought_tokens_are_reported():
    net = Net(ok("hi", finish="MAX_TOKENS"))
    usage = Usage()
    await collect(net.adapter().chat("k", USER, stream=False, usage=usage))
    assert (usage.requests, usage.input_tokens, usage.output_tokens, usage.thought_tokens) == (1, 12, 3, 7)
    assert usage.finish_reason == "length"
    assert usage.model == "gemini-flash-lite-latest"


@pytest.mark.asyncio
async def test_thought_parts_are_not_returned_as_the_answer():
    reply = httpx.Response(
        200,
        json={"candidates": [{"content": {"parts": [{"text": "thinking...", "thought": True}, {"text": "Real answer."}]}, "finishReason": "STOP"}]},
    )
    assert await collect(Net(reply).adapter().chat("k", USER, stream=False)) == "Real answer."


@pytest.mark.asyncio
async def test_a_thinking_config_the_api_rejects_is_dropped_and_not_sent_again():
    net = Net(
        google_error(400, "Unknown name \"thinkingLevel\" at 'generation_config.thinking_config'", "INVALID_ARGUMENT"),
        ok("fine"),
    )
    adapter = net.adapter()
    options = LLMOptions(task="chat", max_output_tokens=50)

    assert await collect(adapter.chat("k", USER, stream=False, options=options)) == "fine"
    assert "thinkingConfig" in net.body(0)["generationConfig"]
    assert "thinkingConfig" not in net.body(1)["generationConfig"]

    await collect(adapter.chat("k", USER, stream=False, options=options))
    assert "thinkingConfig" not in net.body(2)["generationConfig"]  # remembered


# --- blocked / empty ----------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
async def test_an_empty_reply_blocked_by_safety_raises_provider_blocked(stream):
    if stream:
        net = Net(sse(chunk("", finish="SAFETY")))
    else:
        net = Net(httpx.Response(200, json={"candidates": [{"finishReason": "SAFETY"}]}))
    with pytest.raises(ProviderBlockedError):
        await collect(net.adapter().chat("k", USER, stream=stream))


@pytest.mark.asyncio
async def test_a_prompt_blocked_before_generation_raises_provider_blocked():
    net = Net(httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}}))
    with pytest.raises(ProviderBlockedError):
        await collect(net.adapter().chat("k", USER, stream=False))


@pytest.mark.asyncio
async def test_a_truncated_empty_reply_is_returned_for_the_gateway_to_handle():
    net = Net(ok("", finish="MAX_TOKENS"))
    usage = Usage()
    assert await collect(net.adapter().chat("k", USER, stream=False, usage=usage)) == ""
    assert usage.finish_reason == "length"


# --- streaming ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_streaming_yields_text_in_order_and_reports_usage_finish_and_ttft():
    net = Net(
        sse(
            chunk("Hel"),
            chunk("lo"),
            chunk(" there", finish="STOP", usage={"promptTokenCount": 9, "candidatesTokenCount": 4, "thoughtsTokenCount": 2}),
        )
    )
    usage = Usage()
    pieces = [c async for c in net.adapter().chat("k", USER, stream=True, usage=usage)]
    assert pieces == ["Hel", "lo", " there"]
    assert (usage.requests, usage.input_tokens, usage.output_tokens, usage.thought_tokens) == (1, 9, 4, 2)
    assert usage.finish_reason == "stop" and usage.ttft_ms is not None
    assert net.requests[0].url.params["alt"] == "sse"
    assert net.requests[0].url.path.endswith(":streamGenerateContent")


@pytest.mark.asyncio
async def test_streaming_error_status_is_mapped_before_any_text():
    net = Net(google_error(429, "slow down", "RESOURCE_EXHAUSTED"))
    with pytest.raises(ProviderRateLimitError):
        await collect(net.adapter().chat("k", USER, stream=True))


@pytest.mark.asyncio
async def test_streaming_thinking_rejection_self_heals_too():
    net = Net(google_error(400, "thinking_config is not supported for this model", "INVALID_ARGUMENT"), sse(chunk("ok", finish="STOP")))
    assert await collect(net.adapter().chat("k", USER, stream=True, options=LLMOptions(max_output_tokens=20))) == "ok"
    assert "thinkingConfig" not in net.body(1)["generationConfig"]


# --- error mapping -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "status,message,google_status,expected",
    [
        (400, "API key not valid. Please pass a valid API key.", "INVALID_ARGUMENT", ProviderAuthError),
        (400, "Request payload size exceeds the limit", "INVALID_ARGUMENT", ProviderBadRequestError),
        (401, "Unauthenticated", "UNAUTHENTICATED", ProviderAuthError),
        (403, "Permission denied", "PERMISSION_DENIED", ProviderAuthError),
        (404, "models/x is not found", "NOT_FOUND", ProviderConfigError),
        (429, "Quota exceeded", "RESOURCE_EXHAUSTED", ProviderRateLimitError),
        (500, "Internal error", "INTERNAL", ProviderUnavailableError),
        (503, "The model is overloaded", "UNAVAILABLE", ProviderUnavailableError),
        (504, "Deadline exceeded", "DEADLINE_EXCEEDED", ProviderUnavailableError),
    ],
)
def test_error_statuses_map_to_typed_errors(status, message, google_status, expected):
    body = json.dumps({"error": {"code": status, "message": message, "status": google_status}})
    assert isinstance(map_error(status, body.encode()), expected)


def test_a_per_day_quota_failure_is_classified_and_carries_the_retry_hint():
    body = json.dumps(
        {
            "error": {
                "code": 429,
                "message": "You exceeded your current quota",
                "status": "RESOURCE_EXHAUSTED",
                "details": [
                    {"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]},
                    {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "37s"},
                ],
            }
        }
    )
    error = map_error(429, body.encode())
    assert isinstance(error, ProviderRateLimitError)
    assert error.kind == "rpd" and error.retry_after == 37.0


def test_a_per_minute_quota_failure_is_classified_and_retry_after_header_is_used():
    body = json.dumps(
        {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED",
                   "details": [{"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": [{"quotaId": "GenerateRequestsPerMinutePerProjectPerModel"}]}]}}
    )
    error = map_error(429, body.encode(), httpx.Headers({"retry-after": "12"}))
    assert error.kind == "rpm" and error.retry_after == 12.0


def test_a_garbage_error_body_still_maps_to_a_typed_error():
    assert isinstance(map_error(503, b"<html>bad gateway</html>"), ProviderUnavailableError)
    assert isinstance(map_error(500, None), ProviderUnavailableError)


@pytest.mark.asyncio
async def test_timeouts_and_connection_failures_become_typed_errors():
    with pytest.raises(ProviderTimeoutError):
        await collect(Net(httpx.ReadTimeout("slow")).adapter().chat("k", USER, stream=False))
    with pytest.raises(ProviderUnavailableError):
        await collect(Net(httpx.ConnectError("refused")).adapter().chat("k", USER, stream=False))
    with pytest.raises(ProviderTimeoutError):
        await collect(Net(httpx.ReadTimeout("stalled")).adapter().chat("k", USER, stream=True))


# --- embeddings -----------------------------------------------------------------------------------------


def embeddings_reply(count, vector=(3.0, 4.0)):
    return httpx.Response(200, json={"embeddings": [{"values": list(vector)} for _ in range(count)]})


@pytest.mark.asyncio
async def test_embed_many_is_one_batched_request_with_task_type_and_dimensions():
    net = Net(embeddings_reply(3))
    usage = Usage()
    vectors = await net.adapter().embed_many("k", ["a", "b", "c"], usage=usage, kind="query")

    assert len(vectors) == 3 and usage.requests == 1
    request, body = net.requests[0], net.body()
    assert request.url.path.endswith(f"{EMBEDDING_MODEL}:batchEmbedContents")
    assert request.headers["x-goog-api-key"] == "k"
    assert len(body["requests"]) == 3
    first = body["requests"][0]
    assert first["taskType"] == "RETRIEVAL_QUERY"
    assert first["outputDimensionality"] == EMBEDDING_DIMENSIONS
    assert first["model"] == EMBEDDING_MODEL and first["content"]["parts"][0]["text"] == "a"


@pytest.mark.asyncio
async def test_documents_and_queries_use_different_task_types():
    net = Net(embeddings_reply(1))
    adapter = net.adapter()
    await adapter.embed_many("k", ["x"])  # default: document
    await adapter.embed_many("k", ["x"], kind="query")
    assert [net.body(i)["requests"][0]["taskType"] for i in (0, 1)] == ["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"]


@pytest.mark.asyncio
async def test_embeddings_are_l2_normalized():
    vectors = await Net(embeddings_reply(1, (3.0, 4.0))).adapter().embed_many("k", ["x"])
    assert vectors[0] == pytest.approx([0.6, 0.8])
    assert math.sqrt(sum(x * x for x in vectors[0])) == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_a_zero_vector_is_left_alone_instead_of_dividing_by_zero():
    assert (await Net(embeddings_reply(1, (0.0, 0.0))).adapter().embed_many("k", ["x"]))[0] == [0.0, 0.0]


@pytest.mark.asyncio
async def test_more_than_a_hundred_texts_go_out_in_batches_of_a_hundred():
    class Counting(Net):
        def handler(self, request):
            self.requests.append(request)
            return embeddings_reply(len(json.loads(request.content)["requests"]))

    net = Counting(embeddings_reply(1))
    usage = Usage()
    vectors = await net.adapter().embed_many("k", [f"t{i}" for i in range(250)], usage=usage)
    assert len(vectors) == 250
    assert usage.requests == 3
    assert [len(net.body(i)["requests"]) for i in range(3)] == [100, 100, 50]


@pytest.mark.asyncio
async def test_empty_list_makes_no_request():
    net = Net(embeddings_reply(0))
    assert await net.adapter().embed_many("k", []) == []
    assert net.requests == []


@pytest.mark.asyncio
async def test_a_vector_count_mismatch_is_an_error_not_silent_misalignment():
    with pytest.raises(ProviderBadRequestError):
        await Net(embeddings_reply(2)).adapter().embed_many("k", ["a", "b", "c"])


@pytest.mark.asyncio
async def test_embed_errors_are_typed():
    with pytest.raises(ProviderRateLimitError):
        await Net(google_error(429, "quota", "RESOURCE_EXHAUSTED")).adapter().embed_many("k", ["a"])
    with pytest.raises(ProviderAuthError):
        await Net(google_error(403, "denied", "PERMISSION_DENIED")).adapter().embed_many("k", ["a"])


@pytest.mark.asyncio
async def test_embed_single_text_delegates_to_the_batch_path():
    vector = await Net(embeddings_reply(1)).adapter().embed("k", "one")
    assert vector == pytest.approx([0.6, 0.8])
