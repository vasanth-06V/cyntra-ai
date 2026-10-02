import pytest

from app.llm.budget import estimate_tokens
from app.rag import embeddings


class _CountingAdapter:
    def __init__(self):
        self.calls: list[list[str]] = []

    async def embed_many(self, api_key, texts, usage=None):
        self.calls.append(list(texts))
        return [[0.0, 1.0] for _ in texts]


@pytest.fixture
def adapter(monkeypatch):
    fake = _CountingAdapter()
    monkeypatch.setattr(embeddings, "_gemini", fake)
    return fake


@pytest.mark.asyncio
async def test_embed_texts_sends_everything_in_one_adapter_call(adapter):
    vectors = await embeddings.embed_texts("key", [f"chunk {i}" for i in range(8)])

    assert len(vectors) == 8
    assert len(adapter.calls) == 1
    assert len(adapter.calls[0]) == 8


@pytest.mark.asyncio
async def test_oversized_text_is_truncated_so_it_cannot_fail_the_whole_batch(adapter):
    huge = "word " * 20_000  # ~25k tokens, far over the embedding input limit

    await embeddings.embed_texts("key", ["short", huge])

    sent_short, sent_huge = adapter.calls[0]
    assert sent_short == "short"
    assert estimate_tokens(sent_huge) <= embeddings._MAX_INPUT_TOKENS + 5


@pytest.mark.asyncio
async def test_embed_text_is_a_single_item_batch(adapter):
    vector = await embeddings.embed_text("key", "hello")

    assert vector == [0.0, 1.0]
    assert adapter.calls == [["hello"]]
