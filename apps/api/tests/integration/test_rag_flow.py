"""POST /rag/resumes/{id}/process end to end (storage download mocked)."""

import io

import pytest

from app.core import background
from botocore.exceptions import ClientError
from docx import Document
from postgrest.exceptions import APIError

from app.providers.base import ProviderBlockedError
from app.rag import service as rag_service

from .conftest import USER_A, USER_B, as_user, new_id, seed_key


def _docx_bytes(*paragraphs: str) -> bytes:
    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


@pytest.fixture
def r2(monkeypatch):
    """Maps file_key -> bytes; records downloads."""
    store: dict[str, bytes] = {}
    calls: list[str] = []

    def fake_download(key):
        calls.append(key)
        if key not in store:
            raise ClientError({"Error": {"Code": "NoSuchKey", "Message": "missing"}}, "GetObject")
        return store[key]

    monkeypatch.setattr(rag_service, "download_bytes", fake_download)
    store["calls"] = calls  # type: ignore[assignment]
    return store


def _resume(env, user=USER_A, name="r.docx"):
    # Real keys are resumes/<owner>/<file>; the backend refuses any other prefix.
    return env.db.seed("resumes", user_id=user, file_key=f"resumes/{user}/{name}")


async def test_process_resume_parses_chunks_embeds_and_stores_digest(client, env, r2):
    seed_key(env, USER_A, "gemini", "primary", "gem")
    resume = _resume(env)
    r2[resume["file_key"]] = _docx_bytes(
        "Jane Doe", "Experience", "Built Python services on Kubernetes.", "Skills", "Python, Go"
    )

    r = await client.post(f"/rag/resumes/{resume['id']}/process", headers=as_user(USER_A))
    assert r.status_code == 200
    body = r.json()
    assert body["resume_id"] == resume["id"] and body["chunk_count"] >= 2
    await background.drain()  # the digest is made after the resume is already usable

    chunks = env.db.rows("resume_chunks", resume_id=resume["id"])
    assert len(chunks) == body["chunk_count"]
    assert all(c["embedding"] for c in chunks)
    stored = env.db.rows("resumes", id=resume["id"])[0]
    assert "Kubernetes" in stored["parsed_text"]
    assert stored["digest"] == "Senior engineer, 8 years of Python."
    # One batched embedding request for all chunks, one digest call.
    assert len(env.gemini.embed_calls) == 1
    assert len(env.gemini.embed_calls[0].texts) == body["chunk_count"]
    assert [c.options.task for c in env.gemini.chat_calls] == ["extract"]


async def test_reprocessing_replaces_chunks_instead_of_duplicating(client, env, r2):
    seed_key(env, USER_A, "gemini", "primary", "gem")
    resume = _resume(env)
    r2[resume["file_key"]] = _docx_bytes("Experience", "Python work")
    for _ in range(2):
        r = await client.post(f"/rag/resumes/{resume['id']}/process", headers=as_user(USER_A))
        assert r.status_code == 200
    chunks = env.db.rows("resume_chunks", resume_id=resume["id"])
    assert len(chunks) == r.json()["chunk_count"]


async def test_cannot_process_someone_elses_resume(client, env, r2):
    seed_key(env, USER_B, "gemini", "primary", "gem")
    resume = _resume(env, user=USER_A)
    r2[resume["file_key"]] = _docx_bytes("Experience", "x")
    r = await client.post(f"/rag/resumes/{resume['id']}/process", headers=as_user(USER_B))
    assert r.status_code == 404
    assert r2["calls"] == [] and env.gemini.embed_calls == []


async def test_unknown_resume_404_and_missing_gemini_key_412(client, env, r2):
    assert (await client.post(f"/rag/resumes/{new_id()}/process", headers=as_user(USER_A))).status_code == 404
    resume = _resume(env)
    r = await client.post(f"/rag/resumes/{resume['id']}/process", headers=as_user(USER_A))
    assert r.status_code == 412


async def test_empty_document_is_422(client, env, r2):
    seed_key(env, USER_A, "gemini", "primary", "gem")
    resume = _resume(env)
    r2[resume["file_key"]] = _docx_bytes("   ")
    r = await client.post(f"/rag/resumes/{resume['id']}/process", headers=as_user(USER_A))
    assert r.status_code == 422


async def test_digest_failure_is_non_fatal(client, env, r2):
    seed_key(env, USER_A, "gemini", "primary", "gem")
    resume = _resume(env)
    r2[resume["file_key"]] = _docx_bytes("Experience", "Python work")
    env.gemini.script = [ProviderBlockedError("nope")]
    r = await client.post(f"/rag/resumes/{resume['id']}/process", headers=as_user(USER_A))
    assert r.status_code == 200
    assert env.db.rows("resumes", id=resume["id"])[0]["digest"] is None


async def test_embedding_quota_exhausted_is_429_and_nothing_is_written(client, env, r2):
    seed_key(env, USER_A, "gemini", "primary", "gem")
    env.gemini.rate_limited_keys.add("gem")
    resume = _resume(env)
    r2[resume["file_key"]] = _docx_bytes("Experience", "Python work")
    r = await client.post(f"/rag/resumes/{resume['id']}/process", headers=as_user(USER_A))
    assert r.status_code == 429
    assert env.db.rows("resume_chunks") == []
    assert env.db.rows("resumes", id=resume["id"])[0]["parsed_text"] is None


# --------------------------- findings ---------------------------


async def test_corrupt_file_is_clean_4xx(client, env, r2):
    seed_key(env, USER_A, "gemini", "primary", "gem")
    resume = _resume(env)
    r2[resume["file_key"]] = b"this is definitely not a docx"
    r = await client.post(f"/rag/resumes/{resume['id']}/process", headers=as_user(USER_A))
    assert r.status_code < 500


async def test_missing_stored_object_is_not_a_500(client, env, r2):
    seed_key(env, USER_A, "gemini", "primary", "gem")
    resume = _resume(env, name="never-uploaded.pdf")
    r = await client.post(f"/rag/resumes/{resume['id']}/process", headers=as_user(USER_A))
    assert r.status_code != 500


async def test_failed_chunk_insert_must_not_leave_half_processed_resume(client, env, r2):
    seed_key(env, USER_A, "gemini", "primary", "gem")
    resume = _resume(env)
    r2[resume["file_key"]] = _docx_bytes("Experience", "Python work")
    env.db.fail_on[("resume_chunks", "insert")] = APIError({"message": "boom", "code": "XX000"})
    await client.post(f"/rag/resumes/{resume['id']}/process", headers=as_user(USER_A))
    stored = env.db.rows("resumes", id=resume["id"])[0]
    has_chunks = bool(env.db.rows("resume_chunks", resume_id=resume["id"]))
    assert stored["parsed_text"] is None or has_chunks


async def test_enormous_document_is_rejected_or_capped(client, env, r2):
    seed_key(env, USER_A, "gemini", "primary", "gem")
    resume = _resume(env)
    r2[resume["file_key"]] = _docx_bytes(*["lorem ipsum dolor sit amet " * 40] * 800)
    r = await client.post(f"/rag/resumes/{resume['id']}/process", headers=as_user(USER_A))
    texts = sum(len(c.texts) for c in env.gemini.embed_calls)
    assert r.status_code >= 400 or texts <= 100


async def test_a_file_over_500kb_is_rejected_before_parsing_or_embedding(client, env, r2):
    seed_key(env, USER_A, "gemini", "primary", "gem")
    resume = _resume(env)
    r2[resume["file_key"]] = b"x" * (500 * 1024 + 1)
    r = await client.post(f"/rag/resumes/{resume['id']}/process", headers=as_user(USER_A))
    assert r.status_code == 422
    assert "500KB" in r.json()["error"]["message"]
    assert env.gemini.embed_calls == []


async def test_a_bare_404_from_storage_is_reported_as_file_not_found(client, env, monkeypatch):
    from botocore.exceptions import ClientError

    from app.rag import service as rag_service

    def gone(key):
        raise ClientError({"Error": {"Code": "", "Message": ""}, "ResponseMetadata": {"HTTPStatusCode": 404}}, "GetObject")

    monkeypatch.setattr(rag_service, "download_bytes", gone)
    seed_key(env, USER_A, "gemini", "primary", "gem")
    resume = _resume(env)
    r = await client.post(f"/rag/resumes/{resume['id']}/process", headers=as_user(USER_A))
    assert r.status_code == 404


async def test_a_file_reference_outside_the_owners_prefix_is_refused_before_any_download(client, env, r2):
    seed_key(env, USER_A, "gemini", "primary", "gem")
    victim = _resume(env, user=USER_B)
    r2[victim["file_key"]] = _docx_bytes("Experience", "The victim's private resume text")
    for bad in (victim["file_key"], f"resumes/{USER_A}/../{USER_B}/x.docx", "somewhere/else.docx"):
        row = env.db.seed("resumes", user_id=USER_A, file_key=bad)
        r = await client.post(f"/rag/resumes/{row['id']}/process", headers=as_user(USER_A))
        assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_file", bad
    assert r2["calls"] == [] and env.gemini.embed_calls == []  # nothing was fetched or embedded
    assert all(not r["parsed_text"] for r in env.db.rows("resumes", user_id=USER_A))


async def test_extracted_text_is_capped(client, env, r2):
    seed_key(env, USER_A, "gemini", "primary", "gem")
    resume = _resume(env)
    r2[resume["file_key"]] = _docx_bytes("Experience", *["Built Python services on Kubernetes. " * 30] * 60)
    r = await client.post(f"/rag/resumes/{resume['id']}/process", headers=as_user(USER_A))
    assert r.status_code == 200
    assert len(env.db.rows("resumes", id=resume["id"])[0]["parsed_text"]) <= 40_000
