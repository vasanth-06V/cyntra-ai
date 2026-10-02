from datetime import UTC, datetime

import pytest

from app.interviews import service
from app.llm.budget import ensure_user_first
from app.providers.base import Message, MessageRole


async def _value(v):
    return v


def test_ensure_user_first_drops_or_pads_a_leading_assistant_turn():
    a = Message(role=MessageRole.ASSISTANT, content="a")
    u = Message(role=MessageRole.USER, content="u")
    assert ensure_user_first([a, u]) == [u]
    padded = ensure_user_first([a, u], placeholder="(start)")
    assert [m.role for m in padded] == [MessageRole.USER, MessageRole.ASSISTANT, MessageRole.USER]
    assert ensure_user_first([u, a, u]) == [u, a, u]


def test_salvage_opening_never_shows_raw_json():
    salvage = service._salvage_opening
    assert salvage("Hello there!") == "Hello there!"
    assert (
        salvage('{"brief": "x", "opening": "Hi, tell me about \\"you\\".", "extra')
        == 'Hi, tell me about "you".'
    )
    cut_off = salvage('{"brief": "Backend role, senior, Py')
    assert cut_off and not cut_off.startswith("{")


def _interview(phase, itype="coding", question_ids=None):
    return {
        "id": "i-1", "type": itype, "status": "in_progress", "phase": phase,
        "jd_text": "JD", "brief": "b", "provider": "gemini", "resume_id": "r",
        "running_summary": None, "selected_question_ids": question_ids or [],
        "started_at": datetime.now(UTC).isoformat(),
    }


def _wire(monkeypatch, interview, summarizer_fn=None, question_fn=None):
    seen = []

    async def fake_complete(user_id, provider, messages, options=None):
        seen.append(messages)
        return "Next?"

    monkeypatch.setattr(service, "_get_owned_interview", lambda *a: _value(interview))
    monkeypatch.setattr(service, "_update_interview", lambda *a: _value(None))
    monkeypatch.setattr(service, "_next_turn_index", lambda *a: _value(2))
    monkeypatch.setattr(service, "_append_transcript", lambda *a: _value(None))
    monkeypatch.setattr(
        service, "_recent_turns",
        lambda *a: _value([{"speaker": "ai", "text": "Hi"}, {"speaker": "user", "text": "Hello"}]),
    )
    monkeypatch.setattr(
        service.summarizer, "maybe_update_summary", summarizer_fn or (lambda *a: _value(None))
    )
    if question_fn:
        monkeypatch.setattr(service, "_get_question_text", question_fn)
    monkeypatch.setattr(service.gateway, "complete", fake_complete)
    return seen


@pytest.mark.asyncio
async def test_question_not_revealed_during_intro_and_user_turn_comes_first(monkeypatch):
    async def must_not_fetch(qid):
        raise AssertionError("question fetched during intro")

    seen = _wire(monkeypatch, _interview("intro", question_ids=["q-1"]), question_fn=must_not_fetch)

    await service.submit_turn("u", "i-1", "Hello")

    non_system = [m for m in seen[0] if m.role != MessageRole.SYSTEM]
    assert non_system[0].role == MessageRole.USER


@pytest.mark.asyncio
async def test_failed_summary_does_not_fail_the_turn(monkeypatch):
    async def boom(*a):
        raise RuntimeError("quota")

    _wire(monkeypatch, _interview("warm_up", itype="behavioral"), summarizer_fn=boom)

    result = await service.submit_turn("u", "i-1", "Hello")

    assert result["message"] == "Next?"
