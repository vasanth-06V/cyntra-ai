import pytest
from fastapi import HTTPException

from app.db import resumes as resumes_repo
from app.llm.models import EMBEDDING_VERSION
from app.rag import service
from app.rag.resume_chunker import ResumeChunk

RESUME_TEXT = "Experience\nDid things."


async def _async_value(value):
    return value


def _chunks(*bodies):
    return [ResumeChunk("experience", f"Experience\n{b}", b) for b in bodies]


@pytest.fixture(autouse=True)
def _common_mocks(monkeypatch):
    """Everything outside process_resume's own logic is replaced; returns a log."""
    log = {"embeds": [], "replace": [], "resume": {"id": "resume-1", "file_key": "resume-1.docx"}}

    async def get_owned(user_id, resume_id):
        return log["resume"]

    async def fake_embed(user_id, texts, kind="doc"):
        log["embeds"].append((list(texts), kind))
        return [[0.1, 0.2]] * len(texts)

    async def fake_replace(user_id, resume_id, text, content_hash, embed_version, chunks):
        log["replace"].append(
            {"user_id": user_id, "resume_id": resume_id, "text": text, "hash": content_hash,
             "version": embed_version, "chunks": chunks}
        )
        return len(chunks)

    monkeypatch.setattr(service, "_get_owned_resume", get_owned)
    monkeypatch.setattr(service, "get_key_row", lambda *a, **k: _async_value({"id": "k", "encrypted_key": "x"}))
    monkeypatch.setattr(service, "download_bytes", lambda key: b"fake file bytes")
    monkeypatch.setattr(service, "extract_text", lambda filename, data: RESUME_TEXT)
    monkeypatch.setattr(service.gateway, "embed", fake_embed)
    monkeypatch.setattr(resumes_repo, "replace_chunks", fake_replace)
    monkeypatch.setattr(resumes_repo, "chunk_count", lambda resume_id: _async_value(3))
    monkeypatch.setattr(service.background, "schedule", lambda coro, **k: coro.close())
    return log


@pytest.mark.asyncio
async def test_process_resume_embeds_every_chunk_in_one_document_request_and_stores_atomically(monkeypatch, _common_mocks):
    monkeypatch.setattr(service, "chunk_resume", lambda text: _chunks("chunk one", "chunk two"))

    count = await service.process_resume("user-1", "resume-1")

    assert count == 2
    assert _common_mocks["embeds"] == [(["Experience\nchunk one", "Experience\nchunk two"], "doc")]  # one request; header included
    (stored,) = _common_mocks["replace"]
    assert (stored["user_id"], stored["resume_id"], stored["text"]) == ("user-1", "resume-1", RESUME_TEXT)
    assert stored["version"] == EMBEDDING_VERSION and stored["hash"] == service.content_hash(RESUME_TEXT)
    assert stored["chunks"][0] == {"chunk_index": 0, "content": "Experience\nchunk one", "section": "experience", "embedding": [0.1, 0.2]}


@pytest.mark.asyncio
async def test_an_unchanged_resume_is_not_embedded_again(monkeypatch, _common_mocks):
    monkeypatch.setattr(service, "chunk_resume", lambda text: _chunks("chunk one"))
    _common_mocks["resume"].update(parsed_text=RESUME_TEXT, content_hash=service.content_hash(RESUME_TEXT))

    count = await service.process_resume("user-1", "resume-1")

    assert count == 3  # the chunks already stored
    assert _common_mocks["embeds"] == [] and _common_mocks["replace"] == []


@pytest.mark.asyncio
async def test_a_changed_chunker_or_text_triggers_reprocessing(monkeypatch, _common_mocks):
    monkeypatch.setattr(service, "chunk_resume", lambda text: _chunks("chunk one"))
    _common_mocks["resume"].update(parsed_text="old text", content_hash=service.content_hash("old text"))

    await service.process_resume("user-1", "resume-1")

    assert len(_common_mocks["embeds"]) == 1


def test_the_content_hash_covers_chunker_and_embedding_versions(monkeypatch):
    base = service.content_hash("same text")
    monkeypatch.setattr(service, "CHUNKER_VERSION", "99")
    assert service.content_hash("same text") != base
    monkeypatch.undo()
    monkeypatch.setattr(service, "EMBEDDING_VERSION", "other-model:768:v9")
    assert service.content_hash("same text") != base


@pytest.mark.asyncio
async def test_more_than_the_chunk_cap_keeps_the_first_ones(monkeypatch, _common_mocks, caplog):
    monkeypatch.setattr(service, "chunk_resume", lambda text: _chunks(*[f"c{i}" for i in range(75)]))

    count = await service.process_resume("user-1", "resume-1")

    assert count == 60 and len(_common_mocks["embeds"][0][0]) == 60
    assert any("keeping the first 60" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_process_resume_raises_412_without_gemini_key(monkeypatch, _common_mocks):
    monkeypatch.setattr(service, "get_key_row", lambda *a, **kw: _async_value(None))

    with pytest.raises(HTTPException) as exc_info:
        await service.process_resume("user-1", "resume-1")

    assert exc_info.value.status_code == 412


@pytest.mark.asyncio
async def test_process_resume_raises_422_when_no_chunks_extracted(monkeypatch, _common_mocks):
    monkeypatch.setattr(service, "chunk_resume", lambda text: [])

    with pytest.raises(HTTPException) as exc_info:
        await service.process_resume("user-1", "resume-1")

    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_process_resume_raises_404_when_resume_not_owned(monkeypatch, _common_mocks):
    async def raise_not_found(user_id, resume_id):
        raise HTTPException(status_code=404, detail="Resume not found")

    monkeypatch.setattr(service, "_get_owned_resume", raise_not_found)

    with pytest.raises(HTTPException) as exc_info:
        await service.process_resume("user-1", "resume-1")

    assert exc_info.value.status_code == 404
