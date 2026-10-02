from datetime import UTC, datetime, timedelta

import pytest

from app.interviews import service, summarizer
from app.llm.budget import estimate_messages_tokens
from app.llm.json_utils import extract_json
from app.llm.prompts.interview import goal_for, question_index_for
from app.llm.prompts import resume as resume_prompts
from app.rag import service as rag_service


async def _value(v):
    return v


def test_extract_json_shared_helper():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_goal_and_question_index_helpers():
    assert "Wrap up" in goal_for("wrap_up")
    assert goal_for("unknown_phase")
    assert question_index_for("problem_1") == 0
    assert question_index_for("problem_2") == 1
    assert question_index_for("coding") == 0


@pytest.fixture
def start_mocks(monkeypatch):
    calls = {"complete": [], "embed": 0, "updates": {}, "appended": []}

    monkeypatch.setattr(
        service,
        "_get_owned_processed_resume",
        lambda *a: _value({"id": "r", "parsed_text": "text", "digest": "Digest of the candidate."}),
    )
    monkeypatch.setattr(service, "get_key_row", lambda *a: _value({"id": "k"}))
    monkeypatch.setattr(service, "_create_interview_row", lambda *a: _value("i-1"))
    monkeypatch.setattr(service, "match_question_bank", lambda *a, **k: _value([]))
    monkeypatch.setattr(service, "_get_owned_interview", lambda *a: _value({"id": "i-1"}))

    async def fake_embed(user_id, texts):
        calls["embed"] += 1
        return [[0.1] for _ in texts]

    async def fake_update(iid, fields):
        calls["updates"][iid] = fields

    async def fake_append(iid, idx, speaker, text):
        calls["appended"].append((idx, speaker, text))

    monkeypatch.setattr(service.gateway, "embed", fake_embed)
    monkeypatch.setattr(service, "_update_interview", fake_update)
    monkeypatch.setattr(service, "_append_transcript", fake_append)
    return calls


@pytest.mark.asyncio
async def test_setup_is_one_embed_and_one_llm_call_and_stores_brief(monkeypatch, start_mocks):
    async def fake_complete(user_id, provider, messages, options=None):
        start_mocks["complete"].append((messages, options))
        return '{"brief": "Backend role, senior, Python.", "opening": "Hi! Tell me about yourself."}'

    monkeypatch.setattr(service.gateway, "complete", fake_complete)

    await service.start_interview("u", "behavioral", "gemini", "r", "JD " * 5000)

    assert start_mocks["embed"] == 1
    assert len(start_mocks["complete"]) == 1
    messages, options = start_mocks["complete"][0]
    assert options.json_mode is True
    assert estimate_messages_tokens(messages) < 1800  # JD truncated
    assert start_mocks["updates"]["i-1"]["brief"] == "Backend role, senior, Python."
    assert start_mocks["appended"][0] == (0, "ai", "Hi! Tell me about yourself.")


@pytest.mark.asyncio
async def test_setup_falls_back_when_model_ignores_json_format(monkeypatch, start_mocks):
    async def fake_complete(user_id, provider, messages, options=None):
        return "Hello, I'm your interviewer. What brings you here?"

    monkeypatch.setattr(service.gateway, "complete", fake_complete)

    await service.start_interview("u", "behavioral", "gemini", "r", "Backend engineer JD")

    assert start_mocks["appended"][0][2] == "Hello, I'm your interviewer. What brings you here?"
    brief = start_mocks["updates"]["i-1"]["brief"]
    assert "Backend engineer JD" in brief and "Digest of the candidate." in brief


@pytest.mark.asyncio
async def test_turn_prompt_is_lean_single_call_and_injects_question(monkeypatch):
    interview = {
        "id": "i-1",
        "type": "coding",
        "status": "in_progress",
        "phase": "problem_2",
        "jd_text": "HUGE JD " * 3000,
        "brief": "Short brief.",
        "provider": "gemini",
        "resume_id": "r",
        "running_summary": "Covered arrays.",
        "selected_question_ids": ["q-1", "q-2"],
        "started_at": (datetime.now(UTC) - timedelta(minutes=40)).isoformat(),
    }
    seen = []

    async def fake_complete(user_id, provider, messages, options=None):
        seen.append((messages, options))
        return "Next question?"

    asked = []

    async def fake_question(qid):
        asked.append(qid)
        return "Merge two sorted lists."

    long_turns = [
        {"speaker": "ai" if i % 2 == 0 else "user", "text": "word " * 2000} for i in range(6)
    ]
    monkeypatch.setattr(service, "_get_owned_interview", lambda *a: _value(interview))
    monkeypatch.setattr(service, "_update_interview", lambda *a: _value(None))
    monkeypatch.setattr(service, "_next_turn_index", lambda *a: _value(10))
    monkeypatch.setattr(service, "_append_transcript", lambda *a: _value(None))
    monkeypatch.setattr(service, "_recent_turns", lambda *a: _value(long_turns))
    monkeypatch.setattr(service, "_get_question_text", fake_question)
    monkeypatch.setattr(service.summarizer, "maybe_update_summary", lambda *a: _value(None))
    monkeypatch.setattr(service.gateway, "complete", fake_complete)

    await service.submit_turn("u", "i-1", "my answer")

    assert len(seen) == 1  # a turn is exactly one LLM call
    messages, options = seen[0]
    assert estimate_messages_tokens(messages) <= 1200
    assert options.max_output_tokens == 160
    system = messages[0].content
    assert "Short brief." in system and "HUGE JD" not in system
    assert "Merge two sorted lists." in system
    assert asked == ["q-2"]  # problem_2 -> second question
    assert "Covered arrays." in messages[1].content


class _Table:
    def __init__(self, db):
        self.db = db
        self.filters = {}

    def select(self, *a, **k):
        return self

    def update(self, fields):
        self.db["updated"] = fields
        return self

    def eq(self, *a):
        return self

    def gte(self, field, value):
        self.db["gte"] = (field, value)
        return self

    def order(self, *a, **k):
        return self

    def execute(self):
        db = self.db

        class R:
            data = db["turns"]

        return R()


class _DB:
    def __init__(self, turns):
        self.db = {"turns": turns}

    def table(self, name):
        return _Table(self.db)


def _turns(start, n):
    return [
        {"turn_index": start + i, "speaker": "ai" if i % 2 == 0 else "user", "text": f"t{start + i}"}
        for i in range(n)
    ]


@pytest.mark.asyncio
async def test_summarizer_skips_until_enough_new_turns(monkeypatch):
    fake = _DB(_turns(8, 7))
    monkeypatch.setattr(summarizer, "get_supabase", lambda: fake)
    called = []

    async def fake_complete(*a, **k):
        called.append(1)
        return "x"

    monkeypatch.setattr(summarizer.gateway, "complete", fake_complete)

    await summarizer.maybe_update_summary(
        {"id": "i", "summarized_through_turn": 8, "running_summary": "old"}, "u", "gemini"
    )

    assert not called
    assert fake.db["gte"] == ("turn_index", 8)  # only turns since the last summary


@pytest.mark.asyncio
async def test_summarizer_is_incremental_and_advances_marker(monkeypatch):
    fake = _DB(_turns(8, 8))
    monkeypatch.setattr(summarizer, "get_supabase", lambda: fake)
    prompts = []

    async def fake_complete(user_id, provider, messages, options=None):
        prompts.append(messages[0].content)
        return " new summary "

    monkeypatch.setattr(summarizer.gateway, "complete", fake_complete)

    await summarizer.maybe_update_summary(
        {"id": "i", "summarized_through_turn": 8, "running_summary": "old summary"}, "u", "gemini"
    )

    assert "old summary" in prompts[0] and "t8" in prompts[0] and "t0:" not in prompts[0]
    assert fake.db["updated"] == {"running_summary": "new summary", "summarized_through_turn": 16}


@pytest.mark.asyncio
async def test_resume_digest_failure_is_non_fatal(monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("quota")

    monkeypatch.setattr(rag_service.gateway, "complete", boom)
    assert await rag_service._make_digest("u", "resume text") is None


@pytest.mark.asyncio
async def test_resume_digest_returns_text(monkeypatch):
    seen = []

    async def ok(user_id, provider, messages, options=None):
        seen.append(messages[0].content)
        return "  Senior Python dev.  "

    monkeypatch.setattr(rag_service.gateway, "complete", ok)
    assert await rag_service._make_digest("u", "resume text") == "Senior Python dev."
    assert resume_prompts.DIGEST_PROMPT.split("{")[0] in seen[0]
