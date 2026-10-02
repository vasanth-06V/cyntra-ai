import asyncio

import pytest

from app.llm import gateway
from scripts import reembed


@pytest.fixture
def provider(monkeypatch):
    """Counts what actually reaches the embeddings provider."""
    sent: list[tuple[str, list[str]]] = []

    async def fake_uncached(user_id, texts, kind):
        sent.append((kind, list(texts)))
        return [[float(len(t))] for t in texts]

    monkeypatch.setattr(gateway, "_embed_uncached", fake_uncached)
    return sent


# --- query cache ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_repeated_query_is_served_from_memory_with_no_provider_request(provider):
    first = await gateway.embed("u", ["Experience with Python"], kind="query")
    second = await gateway.embed("u", ["Experience with Python"], kind="query")

    assert first == second
    assert provider == [("query", ["Experience with Python"])]  # one request in total


@pytest.mark.asyncio
async def test_only_the_missing_queries_are_requested_and_order_is_preserved(provider):
    await gateway.embed("u", ["a", "bb"], kind="query")
    vectors = await gateway.embed("u", ["bb", "ccc", "a"], kind="query")

    assert vectors == [[2.0], [3.0], [1.0]]
    assert provider[1] == ("query", ["ccc"])


@pytest.mark.asyncio
async def test_documents_are_never_cached(provider):
    await gateway.embed("u", ["same text"], kind="doc")
    await gateway.embed("u", ["same text"], kind="doc")
    assert len(provider) == 2


@pytest.mark.asyncio
async def test_the_cache_is_keyed_by_embedding_version_so_a_model_change_cannot_serve_stale_vectors(provider, monkeypatch):
    await gateway.embed("u", ["x"], kind="query")
    monkeypatch.setattr(gateway, "EMBEDDING_VERSION", "next-model:768:v9")
    await gateway.embed("u", ["x"], kind="query")
    assert len(provider) == 2


@pytest.mark.asyncio
async def test_a_failed_embed_caches_nothing(monkeypatch):
    calls = []

    async def failing(user_id, texts, kind):
        calls.append(1)
        raise RuntimeError("down")

    monkeypatch.setattr(gateway, "_embed_uncached", failing)
    for _ in range(2):
        with pytest.raises(RuntimeError):
            await gateway.embed("u", ["x"], kind="query")
    assert len(calls) == 2


# --- re-embed logic ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_reembed_updates_every_stale_row_in_batches_until_none_remain():
    stale = [{"id": f"r{i}", "content": f"text {i}"} for i in range(5)]
    stored, embed_batches = {}, []

    async def fetch(n):
        return [r for r in stale if r["id"] not in stored][:n]

    async def embed(texts):
        embed_batches.append(list(texts))
        return [[float(i)] for i, _ in enumerate(texts)]

    async def store(row_id, vector):
        stored[row_id] = vector

    async def no_sleep(_):
        pass

    result = await reembed.reembed_rows(fetch, lambda r: r["content"], embed, store, batch=2, sleep=no_sleep)

    assert result == {"stale_at_least": 5, "updated": 5, "requests": 3}
    assert [len(b) for b in embed_batches] == [2, 2, 1]  # one request per batch
    assert set(stored) == {r["id"] for r in stale}


@pytest.mark.asyncio
async def test_a_dry_run_changes_and_requests_nothing():
    async def fetch(n):
        return [{"id": "r1", "content": "x"}]

    async def must_not_run(*a, **k):
        raise AssertionError("a dry run must not embed or store")

    result = await reembed.reembed_rows(fetch, lambda r: r["content"], must_not_run, must_not_run, apply=False)
    assert result == {"stale_at_least": 1, "updated": 0, "requests": 0}


@pytest.mark.asyncio
async def test_nothing_stale_means_nothing_to_do():
    async def fetch(n):
        return []

    assert await reembed.reembed_rows(fetch, str, None, None) == {"stale_at_least": 0, "updated": 0, "requests": 0}


def test_the_reembed_script_refuses_to_run_without_a_key_in_the_environment(monkeypatch, capsys):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr("sys.argv", ["reembed"])
    assert asyncio.run(reembed.main()) == 2
    assert "GEMINI_API_KEY" in capsys.readouterr().out
