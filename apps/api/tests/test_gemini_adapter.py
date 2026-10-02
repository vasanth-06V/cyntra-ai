import pytest
from google.api_core.exceptions import InvalidArgument, PermissionDenied, ResourceExhausted

from app.providers import gemini
from app.providers.base import ProviderRateLimitError
from app.providers.gemini import GeminiAdapter


class _FakeModel:
    def __init__(self, error: Exception | None):
        self._error = error

    async def generate_content_async(self, *args, **kwargs):
        if self._error:
            raise self._error
        return object()


def _patch_model(monkeypatch, error: Exception | None):
    monkeypatch.setattr(gemini.genai, "configure", lambda **kw: None)
    monkeypatch.setattr(gemini.genai, "GenerativeModel", lambda *a, **kw: _FakeModel(error))


@pytest.mark.asyncio
async def test_validate_true_for_a_working_key(monkeypatch):
    _patch_model(monkeypatch, None)
    assert await GeminiAdapter().validate("key") is True


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [InvalidArgument("API key not valid"), PermissionDenied("denied")])
async def test_validate_false_when_google_rejects_the_key(monkeypatch, error):
    # Google reports a bad/malformed key as InvalidArgument, not as an auth error.
    _patch_model(monkeypatch, error)
    assert await GeminiAdapter().validate("bad-key") is False


@pytest.mark.asyncio
async def test_validate_raises_rate_limit_distinct_from_invalid_key(monkeypatch):
    _patch_model(monkeypatch, ResourceExhausted("quota"))
    with pytest.raises(ProviderRateLimitError):
        await GeminiAdapter().validate("key")


@pytest.mark.asyncio
async def test_embed_requests_768_dimensions_to_match_the_schema(monkeypatch):
    captured = {}

    def fake_embed_content(**kwargs):
        captured.update(kwargs)
        return {"embedding": [0.0] * 768}

    monkeypatch.setattr(gemini.genai, "configure", lambda **kw: None)
    monkeypatch.setattr(gemini.genai, "embed_content", fake_embed_content)

    vector = await GeminiAdapter().embed("key", "hello")

    assert len(vector) == 768
    assert captured["output_dimensionality"] == 768
    assert captured["model"] == "models/gemini-embedding-001"


def test_does_not_use_retired_model_names():
    assert "1.5" not in gemini._MODEL_NAME
    assert "text-embedding-004" not in gemini._EMBEDDING_MODEL
