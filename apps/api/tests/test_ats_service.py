import pytest
from fastapi import HTTPException

from app.ats import service
from app.keys.service import BothKeysFailedError


async def _async_value(value):
    return value


def _gemini_key_row():
    return {"id": "key-1", "encrypted_key": "gemini-key"}


@pytest.fixture(autouse=True)
def _common_mocks(monkeypatch):
    monkeypatch.setattr(service, "decrypt_key", lambda encrypted: encrypted)
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
    monkeypatch.setattr(service, "embed_text", lambda api_key, text: _async_value([0.1, 0.2]))
    monkeypatch.setattr(
        service,
        "match_resume_chunks",
        lambda resume_id, embedding, match_count=1: _async_value(
            [{"id": "chunk-1", "content": "Python and SQL work.", "similarity": 0.8}]
        ),
    )


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
    assert result["semantic_score"] == pytest.approx(0.8)


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
        raise BothKeysFailedError("both keys rate-limited")

    monkeypatch.setattr(service, "extract_requirements", fake_extract_requirements)

    with pytest.raises(HTTPException) as exc_info:
        await service.score_resume("user-1", "resume-1", "gemini", "some JD")

    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_score_resume_raises_429_when_feedback_generation_exhausts_both_keys(monkeypatch):
    async def fake_extract_requirements(user_id, provider, jd_text):
        return {"must_have": [], "nice_to_have": [], "experience_level": "mid", "title": "Eng"}

    async def fake_generate_feedback(*args, **kwargs):
        raise BothKeysFailedError("both keys rate-limited")

    monkeypatch.setattr(service, "extract_requirements", fake_extract_requirements)
    monkeypatch.setattr(service, "generate_feedback", fake_generate_feedback)

    with pytest.raises(HTTPException) as exc_info:
        await service.score_resume("user-1", "resume-1", "gemini", "some JD")

    assert exc_info.value.status_code == 429
