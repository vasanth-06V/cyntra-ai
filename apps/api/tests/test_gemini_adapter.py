import pytest
from google.api_core.exceptions import (
    InvalidArgument,
    PermissionDenied,
    ResourceExhausted,
    ServiceUnavailable,
)

from app.llm.models import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL
from app.llm.options import LLMOptions, Usage
from app.providers import gemini
from app.providers.base import (
    Message,
    MessageRole,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderUnavailableError,
)
from app.providers.gemini import GeminiAdapter


@pytest.fixture(autouse=True)
def _fresh_client_cache():
    gemini._generative_client.cache_clear()
    gemini._model_client.cache_clear()
    yield
    gemini._generative_client.cache_clear()
    gemini._model_client.cache_clear()


# --- validate: lists models, never generates ---


def _patch_list_models(monkeypatch, error: Exception | None):
    monkeypatch.setattr(gemini, "_model_client", lambda key: object())

    def fake_list_models(page_size=None, client=None):
        if error:
            raise error
        return iter([object()])

    monkeypatch.setattr(gemini.genai, "list_models", fake_list_models)


@pytest.mark.asyncio
async def test_validate_true_for_a_working_key(monkeypatch):
    _patch_list_models(monkeypatch, None)
    assert await GeminiAdapter().validate("key") is True


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [InvalidArgument("API key not valid"), PermissionDenied("denied")])
async def test_validate_false_when_google_rejects_the_key(monkeypatch, error):
    # Google reports a bad/malformed key as InvalidArgument, not as an auth error.
    _patch_list_models(monkeypatch, error)
    assert await GeminiAdapter().validate("bad-key") is False


@pytest.mark.asyncio
async def test_validate_raises_rate_limit_distinct_from_invalid_key(monkeypatch):
    _patch_list_models(monkeypatch, ResourceExhausted("quota"))
    with pytest.raises(ProviderRateLimitError):
        await GeminiAdapter().validate("key")


@pytest.mark.asyncio
async def test_validate_maps_transient_outage(monkeypatch):
    _patch_list_models(monkeypatch, ServiceUnavailable("high demand"))
    with pytest.raises(ProviderUnavailableError):
        await GeminiAdapter().validate("key")


# --- chat: options, system messages, usage, errors ---


class _Meta:
    prompt_token_count = 120
    candidates_token_count = 30


class _Response:
    text = "hello"
    usage_metadata = _Meta()

    def __init__(self, chunks=("he", "llo")):
        self._chunks = chunks

    def __aiter__(self):
        async def gen():
            for c in self._chunks:
                yield type("Chunk", (), {"text": c})()

        return gen()


class _FakeModel:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.calls: list[dict] = []

    async def generate_content_async(self, contents, stream=False, generation_config=None):
        self.calls.append({"contents": contents, "stream": stream, "config": generation_config})
        if self.error:
            raise self.error
        return _Response()


def _patch_model(monkeypatch, model: _FakeModel, captured: dict | None = None):
    def fake_build(api_key, model_name, system_instruction):
        if captured is not None:
            captured.update(api_key=api_key, model=model_name, system=system_instruction)
        return model

    monkeypatch.setattr(gemini, "_build_model", fake_build)


async def _collect(agen) -> str:
    return "".join([c async for c in agen])


@pytest.mark.asyncio
async def test_chat_passes_options_as_generation_config_and_picks_the_task_model(monkeypatch):
    model, captured = _FakeModel(), {}
    _patch_model(monkeypatch, model, captured)
    options = LLMOptions(task="extract", max_output_tokens=200, temperature=0.2, json_mode=True)

    await _collect(
        GeminiAdapter().chat("key", [Message(MessageRole.USER, "hi")], stream=False, options=options)
    )

    assert model.calls[0]["config"] == {
        "max_output_tokens": 200,
        "temperature": 0.2,
        "response_mime_type": "application/json",
    }
    assert captured["model"] == "gemini-flash-lite-latest"


@pytest.mark.asyncio
async def test_chat_without_options_sends_no_generation_config(monkeypatch):
    model = _FakeModel()
    _patch_model(monkeypatch, model)

    await _collect(GeminiAdapter().chat("key", [Message(MessageRole.USER, "hi")], stream=False))

    assert model.calls[0]["config"] is None


@pytest.mark.asyncio
async def test_chat_joins_every_system_message_instead_of_the_last_one_winning(monkeypatch):
    model, captured = _FakeModel(), {}
    _patch_model(monkeypatch, model, captured)
    messages = [
        Message(MessageRole.SYSTEM, "You are the interviewer."),
        Message(MessageRole.SYSTEM, "Summary so far: strong on Python."),
        Message(MessageRole.USER, "hi"),
    ]

    await _collect(GeminiAdapter().chat("key", messages, stream=False))

    assert "You are the interviewer." in captured["system"]
    assert "Summary so far: strong on Python." in captured["system"]


@pytest.mark.asyncio
async def test_chat_records_provider_reported_usage(monkeypatch):
    _patch_model(monkeypatch, _FakeModel())
    usage = Usage()

    await _collect(
        GeminiAdapter().chat("key", [Message(MessageRole.USER, "hi")], stream=True, usage=usage)
    )

    assert usage == Usage(requests=1, input_tokens=120, output_tokens=30)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (PermissionDenied("no"), ProviderAuthError),
        (ResourceExhausted("quota"), ProviderRateLimitError),
        (ServiceUnavailable("busy"), ProviderUnavailableError),
    ],
)
async def test_chat_maps_google_errors(monkeypatch, error, expected):
    _patch_model(monkeypatch, _FakeModel(error=error))
    with pytest.raises(expected):
        await _collect(GeminiAdapter().chat("key", [Message(MessageRole.USER, "hi")], stream=False))


# --- per-key client isolation (the cross-user key-mixing fix) ---


def test_model_gets_a_client_built_from_its_own_key_not_the_global_default(monkeypatch):
    built = []

    def fake_client(client_options):
        client = object()
        built.append((client_options.api_key, client))
        return client

    monkeypatch.setattr(gemini.glm, "GenerativeServiceAsyncClient", fake_client)

    model_a = gemini._build_model("key-A", "m", None)
    model_b = gemini._build_model("key-B", "m", None)

    assert model_a._async_client is not model_b._async_client
    assert [k for k, _ in built] == ["key-A", "key-B"]


def test_the_same_key_reuses_one_client(monkeypatch):
    calls = []
    monkeypatch.setattr(
        gemini.glm,
        "GenerativeServiceAsyncClient",
        lambda client_options: calls.append(client_options.api_key) or object(),
    )

    gemini._build_model("key-A", "m", None)
    gemini._build_model("key-A", "m", None)

    assert calls == ["key-A"]


def test_sdk_canary_model_builds_its_client_lazily_so_overriding_it_is_safe():
    # _build_model relies on this private attribute being None until first
    # use. If an SDK upgrade changes that, this fails loudly instead of the
    # per-key client silently being ignored.
    import google.generativeai as genai

    assert genai.GenerativeModel("any-model")._async_client is None
    assert hasattr(genai, "embed_content_async")


# --- embed_many: one request for the whole list ---


@pytest.mark.asyncio
async def test_embed_many_sends_one_batched_request_with_the_callers_own_client(monkeypatch):
    captured = {}
    sentinel_client = object()

    async def fake_embed(**kwargs):
        captured.update(kwargs)
        return {"embedding": [[0.0] * EMBEDDING_DIMENSIONS for _ in kwargs["content"]]}

    monkeypatch.setattr(gemini, "_generative_client", lambda key: sentinel_client)
    monkeypatch.setattr(gemini.genai, "embed_content_async", fake_embed)
    usage = Usage()

    vectors = await GeminiAdapter().embed_many("key", ["a", "b", "c"], usage=usage)

    assert len(vectors) == 3 and len(vectors[0]) == EMBEDDING_DIMENSIONS
    assert captured["content"] == ["a", "b", "c"]
    assert captured["model"] == EMBEDDING_MODEL
    assert captured["output_dimensionality"] == EMBEDDING_DIMENSIONS
    assert captured["client"] is sentinel_client
    assert usage.requests == 1


@pytest.mark.asyncio
async def test_embed_many_counts_one_request_per_hundred_texts(monkeypatch):
    async def fake_embed(**kwargs):
        return {"embedding": [[0.0] for _ in kwargs["content"]]}

    monkeypatch.setattr(gemini, "_generative_client", lambda key: object())
    monkeypatch.setattr(gemini.genai, "embed_content_async", fake_embed)
    usage = Usage()

    await GeminiAdapter().embed_many("key", ["t"] * 250, usage=usage)

    assert usage.requests == 3


@pytest.mark.asyncio
async def test_embed_many_empty_list_makes_no_request(monkeypatch):
    async def boom(**kwargs):
        raise AssertionError("must not call the API for an empty list")

    monkeypatch.setattr(gemini.genai, "embed_content_async", boom)

    assert await GeminiAdapter().embed_many("key", []) == []


@pytest.mark.asyncio
async def test_embed_many_rejects_a_vector_count_mismatch(monkeypatch):
    async def fake_embed(**kwargs):
        return {"embedding": [[0.0]]}

    monkeypatch.setattr(gemini, "_generative_client", lambda key: object())
    monkeypatch.setattr(gemini.genai, "embed_content_async", fake_embed)

    with pytest.raises(ValueError, match="mismatch"):
        await GeminiAdapter().embed_many("key", ["a", "b"])


@pytest.mark.asyncio
async def test_embed_single_text_delegates_to_the_batch_path(monkeypatch):
    async def fake_embed(**kwargs):
        return {"embedding": [[1.0, 2.0]]}

    monkeypatch.setattr(gemini, "_generative_client", lambda key: object())
    monkeypatch.setattr(gemini.genai, "embed_content_async", fake_embed)

    assert await GeminiAdapter().embed("key", "hello") == [1.0, 2.0]
