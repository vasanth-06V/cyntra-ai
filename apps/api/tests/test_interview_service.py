from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException

from app.interviews import service


async def _async_value(value):
    return value


def _resume_row():
    return {"id": "resume-1", "parsed_text": "Python developer with 5 years experience."}


def _gemini_key_row():
    return {"id": "key-1", "encrypted_key": "gemini-key"}


@pytest.fixture(autouse=True)
def _common_mocks(monkeypatch):
    monkeypatch.setattr(service, "decrypt_key", lambda encrypted: encrypted)
    monkeypatch.setattr(
        service, "_get_owned_processed_resume", lambda user_id, resume_id: _async_value(_resume_row())
    )
    monkeypatch.setattr(
        service, "get_key_row", lambda user_id, provider, slot: _async_value(_gemini_key_row())
    )
    monkeypatch.setattr(service, "embed_text", lambda api_key, text: _async_value([0.1, 0.2]))
    monkeypatch.setattr(
        service, "match_question_bank", lambda *a, **kw: _async_value([{"id": "q-1"}, {"id": "q-2"}])
    )
    monkeypatch.setattr(
        service,
        "match_resume_chunks",
        lambda *a, **kw: _async_value([{"content": "Relevant resume section."}]),
    )
    monkeypatch.setattr(
        service, "summarizer", type("S", (), {"maybe_update_summary": staticmethod(lambda *a: _async_value(None))})
    )


@pytest.mark.asyncio
async def test_start_interview_creates_in_progress_interview_with_opening_message(monkeypatch):
    created = {}
    appended = []
    updated = {}

    async def fake_create_row(user_id, interview_type, jd_text, resume_id, provider):
        created["args"] = (user_id, interview_type, jd_text, resume_id, provider)
        return "interview-1"

    async def fake_update(interview_id, fields):
        updated[interview_id] = fields

    async def fake_append(interview_id, turn_index, speaker, text):
        appended.append((interview_id, turn_index, speaker, text))

    async def fake_get_owned(user_id, interview_id):
        return {"id": interview_id, "status": "in_progress", **updated.get(interview_id, {})}

    async def fake_complete_text(user_id, provider, messages):
        return "Hi! Let's start with a quick intro -- tell me about yourself."

    monkeypatch.setattr(service, "_create_interview_row", fake_create_row)
    monkeypatch.setattr(service, "_update_interview", fake_update)
    monkeypatch.setattr(service, "_append_transcript", fake_append)
    monkeypatch.setattr(service, "_get_owned_interview", fake_get_owned)
    monkeypatch.setattr(service, "complete_text", fake_complete_text)

    result = await service.start_interview(
        "user-1", "coding", "gemini", "resume-1", "We need a backend engineer."
    )

    assert created["args"] == ("user-1", "coding", "We need a backend engineer.", "resume-1", "gemini")
    assert updated["interview-1"]["status"] == "in_progress"
    assert updated["interview-1"]["phase"] == "intro"
    assert updated["interview-1"]["selected_question_ids"] == ["q-1", "q-2"]
    assert appended[0][1:] == (0, "ai", "Hi! Let's start with a quick intro -- tell me about yourself.")
    assert result["status"] == "in_progress"


@pytest.mark.asyncio
async def test_start_interview_marks_aborted_on_failure(monkeypatch):
    updated = {}

    async def fake_create_row(*a):
        return "interview-1"

    async def fake_update(interview_id, fields):
        updated[interview_id] = fields

    async def fake_complete_text(*a):
        raise RuntimeError("provider exploded")

    monkeypatch.setattr(service, "_create_interview_row", fake_create_row)
    monkeypatch.setattr(service, "_update_interview", fake_update)
    monkeypatch.setattr(service, "_append_transcript", lambda *a: _async_value(None))
    monkeypatch.setattr(service, "complete_text", fake_complete_text)

    with pytest.raises(RuntimeError):
        await service.start_interview("user-1", "coding", "gemini", "resume-1", "JD text")

    assert updated["interview-1"] == {"status": "aborted"}


@pytest.mark.asyncio
async def test_submit_turn_advances_phase_and_returns_ai_reply(monkeypatch):
    started_at = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
    interview = {
        "id": "interview-1",
        "type": "coding",
        "status": "in_progress",
        "phase": "intro",  # stale -- 10 minutes in should now be problem_1
        "jd_text": "JD text",
        "provider": "gemini",
        "resume_id": "resume-1",
        "running_summary": None,
        "started_at": started_at,
    }
    updated = {}
    appended = []

    monkeypatch.setattr(service, "_get_owned_interview", lambda *a: _async_value(interview))
    monkeypatch.setattr(service, "_update_interview", lambda iid, fields: _record_update(updated, iid, fields))
    monkeypatch.setattr(service, "_next_turn_index", lambda iid: _async_value(2))
    monkeypatch.setattr(
        service, "_append_transcript", lambda iid, idx, speaker, text: _record_append(appended, iid, idx, speaker, text)
    )
    monkeypatch.setattr(service, "_recent_turns", lambda iid, limit: _async_value([
        {"speaker": "ai", "text": "Tell me about yourself."},
        {"speaker": "user", "text": "I'm a backend engineer."},
    ]))

    async def fake_complete_text(user_id, provider, messages):
        return "Great, let's dive into the first problem."

    monkeypatch.setattr(service, "complete_text", fake_complete_text)

    result = await service.submit_turn("user-1", "interview-1", "I'm a backend engineer.")

    assert result["phase"] == "problem_1"
    assert result["message"] == "Great, let's dive into the first problem."
    assert result["is_final_phase"] is False
    assert updated["interview-1"]["phase"] == "problem_1"
    assert appended[0] == ("interview-1", 2, "user", "I'm a backend engineer.")
    assert appended[1] == ("interview-1", 3, "ai", "Great, let's dive into the first problem.")


@pytest.mark.asyncio
async def test_submit_turn_rejects_when_not_in_progress(monkeypatch):
    interview = {"id": "interview-1", "status": "completed"}
    monkeypatch.setattr(service, "_get_owned_interview", lambda *a: _async_value(interview))

    with pytest.raises(HTTPException) as exc_info:
        await service.submit_turn("user-1", "interview-1", "hello")

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_complete_interview_sets_status(monkeypatch):
    interview = {"id": "interview-1", "status": "in_progress"}
    updated = {}
    monkeypatch.setattr(service, "_get_owned_interview", lambda *a: _async_value(interview))
    monkeypatch.setattr(service, "_update_interview", lambda iid, fields: _record_update(updated, iid, fields))

    result = await service.complete_interview("user-1", "interview-1")

    assert result["status"] == "completed"
    assert updated["interview-1"] == {"status": "completed"}


async def _record_update(store, interview_id, fields):
    store[interview_id] = fields


async def _record_append(store, interview_id, turn_index, speaker, text):
    store.append((interview_id, turn_index, speaker, text))
