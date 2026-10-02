import pytest
from fastapi import HTTPException

from app.ats import service


async def _async_value(value):
    return value


def _gemini_key_row():
    return {"id": "key-1", "encrypted_key": "gemini-key"}


embed_calls: list[list[str]] = []
multi_calls: list[tuple] = []


@pytest.fixture(autouse=True)
def _common_mocks(monkeypatch):
    monkeypatch.setattr(
        service,
        "_get_owned_resume",
        lambda user_id, resume_id: _async_value(
            {"id": resume_id, "parsed_text": "Experience\nPython and SQL work."}
        ),
    )
    monkeypatch.setattr(
        service, "get_key_row", lambda user_id, provider, slot: _async_value(_gemini_key_row())
    )
    embed_calls.clear()

    async def fake_embed(user_id, texts, kind="doc"):
        embed_calls.append(list(texts))
        return [[0.1, 0.2] for _ in texts]

    monkeypatch.setattr(service.gateway, "embed", fake_embed)
    async def fake_multi(resume_id, embeddings, terms, per_query=1):
        multi_calls.append((list(terms), len(embeddings)))
        rows = []
        for i, term in enumerate(terms):
            present = term.lower() in ("python", "sql")
            rows.append({
                "q_idx": i, "chunk_id": f"c{i}", "section": "experience",
                "content": "Python and SQL work.", "similarity": 0.8 if present else 0.4,
                "kw_hit": present, "kw_any": present,
            })
        return rows

    multi_calls.clear()
    monkeypatch.setattr(service, "match_resume_chunks_multi", fake_multi)


@pytest.mark.asyncio
async def test_score_resume_success_returns_full_breakdown(monkeypatch):
    async def fake_extract_requirements(user_id, provider, jd_text):
        return {
            "must_have": ["Python"],
            "nice_to_have": ["Docker"],
            "experience_level": "mid",
            "title": "Backend Engineer",
        }

    async def fake_generate_feedback(*args, **kwargs):
        return "Add Docker experience to your resume."

    monkeypatch.setattr(service, "extract_requirements", fake_extract_requirements)
    monkeypatch.setattr(service, "generate_feedback", fake_generate_feedback)

    result = await service.score_resume("user-1", "resume-1", "gemini", "some JD")

    assert result["missing_must_have"] == []
    assert result["missing_nice_to_have"] == ["Docker"]
    assert result["feedback"] == "Add Docker experience to your resume."
    assert 0 <= result["composite_score"] <= 100
    # Python is backed up (weight 2 -> 1.0); Docker is not (weight 1 -> 0): (2*1 + 1*0) / 3
    assert result["semantic_score"] == pytest.approx(2 / 3)
    assert [c["term"] for c in result["coverage"]] == ["Python", "Docker"]
    assert result["coverage"][0]["covered"] is True and result["coverage"][1]["covered"] is False


@pytest.mark.asyncio
async def test_score_resume_raises_404_when_resume_not_owned(monkeypatch):
    async def raise_not_found(user_id, resume_id):
        raise HTTPException(status_code=404, detail="Resume not found")

    monkeypatch.setattr(service, "_get_owned_resume", raise_not_found)

    with pytest.raises(HTTPException) as exc_info:
        await service.score_resume("user-1", "resume-1", "gemini", "some JD")

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_score_resume_raises_412_without_gemini_key(monkeypatch):
    monkeypatch.setattr(service, "get_key_row", lambda *a, **kw: _async_value(None))

    with pytest.raises(HTTPException) as exc_info:
        await service.score_resume("user-1", "resume-1", "gemini", "some JD")

    assert exc_info.value.status_code == 412


@pytest.mark.asyncio
async def test_score_resume_raises_429_when_extraction_exhausts_both_keys(monkeypatch):
    async def fake_extract_requirements(user_id, provider, jd_text):
        raise HTTPException(status_code=429, detail="both keys rate-limited")

    monkeypatch.setattr(service, "extract_requirements", fake_extract_requirements)

    with pytest.raises(HTTPException) as exc_info:
        await service.score_resume("user-1", "resume-1", "gemini", "some JD")

    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_score_resume_raises_429_when_feedback_generation_exhausts_both_keys(monkeypatch):
    async def fake_extract_requirements(user_id, provider, jd_text):
        return {"must_have": ["python"], "nice_to_have": [], "experience_level": "mid", "title": "Eng"}

    async def fake_generate_feedback(*args, **kwargs):
        raise HTTPException(status_code=429, detail="both keys rate-limited")

    monkeypatch.setattr(service, "extract_requirements", fake_extract_requirements)
    monkeypatch.setattr(service, "generate_feedback", fake_generate_feedback)

    with pytest.raises(HTTPException) as exc_info:
        await service.score_resume("user-1", "resume-1", "gemini", "some JD")

    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_all_requirements_are_one_embedding_request_and_one_retrieval_call(monkeypatch):
    # The free tier counts requests, not texts: 18 requirements must be 1 request.
    keywords = [f"skill-{i}" for i in range(18)]

    async def fake_extract_requirements(user_id, provider, jd_text):
        return {"must_have": keywords[:12], "nice_to_have": keywords[12:], "experience_level": "mid", "title": "Eng"}

    async def fake_generate_feedback(*args, **kwargs):
        return "ok"

    monkeypatch.setattr(service, "extract_requirements", fake_extract_requirements)
    monkeypatch.setattr(service, "generate_feedback", fake_generate_feedback)

    await service.score_resume("user-1", "resume-1", "gemini", "some JD")

    assert len(embed_calls) == 1
    assert embed_calls[0] == [f"Experience with {k}" for k in keywords]  # query-style sentences
    assert len(multi_calls) == 1 and multi_calls[0][1] == 18  # one DB call carrying all 18 vectors
