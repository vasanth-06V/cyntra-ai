import pytest
from fastapi import HTTPException

from app.rag import service


@pytest.fixture(autouse=True)
def _common_mocks(monkeypatch):
    monkeypatch.setattr(service, "decrypt_key", lambda encrypted: encrypted)
    monkeypatch.setattr(
        service,
        "_get_owned_resume",
        lambda user_id, resume_id: _async_value({"id": resume_id, "file_key": f"{resume_id}.docx"}),
    )
    monkeypatch.setattr(
        service, "get_key_row", lambda user_id, provider, slot: _async_value(_gemini_key_row())
    )
    monkeypatch.setattr(service, "download_bytes", lambda key: b"fake file bytes")
    monkeypatch.setattr(service, "extract_text", lambda filename, data: "Experience\nDid things.")

    stored = {}

    def fake_store_setup(monkeypatch_inner=None):
        pass

    monkeypatch.setattr(service, "get_supabase", lambda: _FakeSupabase(stored))
    return stored


async def _async_value(value):
    return value


def _gemini_key_row():
    return {"id": "key-1", "encrypted_key": "gemini-key"}


class _FakeTable:
    def __init__(self, name, stored):
        self.name = name
        self.stored = stored

    def update(self, data):
        self.stored.setdefault("updates", []).append((self.name, data))
        return self

    def delete(self):
        self.stored.setdefault("deletes", []).append(self.name)
        return self

    def insert(self, data):
        self.stored.setdefault("inserts", []).append((self.name, data))
        return self

    def eq(self, *a, **kw):
        return self

    def execute(self):
        return None


class _FakeSupabase:
    def __init__(self, stored):
        self.stored = stored

    def table(self, name):
        return _FakeTable(name, self.stored)


@pytest.mark.asyncio
async def test_process_resume_success_stores_chunks_and_embeddings(monkeypatch, _common_mocks):
    embed_requests = []

    async def fake_embed_texts(api_key, chunks):
        assert api_key == "gemini-key"
        embed_requests.append(list(chunks))
        return [[0.1, 0.2]] * len(chunks)

    monkeypatch.setattr(service, "embed_texts", fake_embed_texts)
    monkeypatch.setattr(service, "chunk_text", lambda text: ["chunk one", "chunk two"])

    count = await service.process_resume("user-1", "resume-1")

    assert count == 2
    assert embed_requests == [["chunk one", "chunk two"]]  # all chunks, one request
    inserts = _common_mocks["inserts"]
    assert inserts[0][0] == "resume_chunks"
    inserted_rows = inserts[0][1]
    assert len(inserted_rows) == 2
    assert inserted_rows[0]["chunk_index"] == 0
    assert inserted_rows[0]["content"] == "chunk one"
    assert inserted_rows[0]["embedding"] == [0.1, 0.2]
    assert _common_mocks["deletes"] == ["resume_chunks"]
    assert _common_mocks["updates"][0][0] == "resumes"


@pytest.mark.asyncio
async def test_process_resume_raises_412_without_gemini_key(monkeypatch, _common_mocks):
    monkeypatch.setattr(service, "get_key_row", lambda *a, **kw: _async_value(None))

    with pytest.raises(HTTPException) as exc_info:
        await service.process_resume("user-1", "resume-1")

    assert exc_info.value.status_code == 412


@pytest.mark.asyncio
async def test_process_resume_raises_422_when_no_chunks_extracted(monkeypatch, _common_mocks):
    monkeypatch.setattr(service, "chunk_text", lambda text: [])

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
