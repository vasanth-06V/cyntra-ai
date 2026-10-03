"""Regression tests for the findings of the project-wide audit (2026-10-04).
Each test names the finding it pins down."""

import json
from datetime import UTC, datetime, timedelta

import pytest

from app.core import background
from app.interviews.service import _MIN_HISTORY_TOKENS, _PROMPT_BUDGET_TOKENS
from app.llm.budget import estimate_messages_tokens, fit_to_budget
from app.providers.base import (
    Message,
    MessageRole,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)

from .conftest import USER_A, USER_B, as_user, seed_key, seed_processed_resume


def _ago(**kw):
    return (datetime.now(UTC) - timedelta(**kw)).isoformat()


# H1 -- deleting a resume clears interviews.resume_id (ON DELETE SET NULL); nothing may 500.
async def test_h1_interviews_whose_resume_was_deleted_still_list_open_and_complete(client, env):
    seed_key(env, USER_A, "gemini", "primary", "gem")
    iv = env.db.seed("interviews", user_id=USER_A, type="hr", jd_text="x", resume_id=None, status="in_progress",
                     phase="warm_up", started_at=_ago(minutes=5), ends_at=_ago(minutes=-55), provider="gemini")
    listed = await client.get("/interviews", headers=as_user(USER_A))
    assert listed.status_code == 200 and listed.json()[0]["resume_id"] is None
    one = await client.get(f"/interviews/{iv['id']}", headers=as_user(USER_A))
    assert one.status_code == 200 and one.json()["resume_id"] is None
    done = await client.post(f"/interviews/{iv['id']}/complete", headers=as_user(USER_A))
    assert done.status_code == 200 and done.json()["status"] == "completed"


# L5 -- a malformed resume id is a clean 422, not a 500.
async def test_l5_a_non_uuid_resume_id_is_422(client, env):
    seed_key(env, USER_A, "gemini", "primary", "gem")
    body = {"resume_id": "not-a-uuid", "jd_text": "A job description here", "provider": "gemini"}
    assert (await client.post("/ats/score", json=body, headers=as_user(USER_A))).status_code == 422
    start = {"type": "hr", "provider": "gemini", "resume_id": "not-a-uuid", "jd_text": "A job description here"}
    assert (await client.post("/interviews", json=start, headers=as_user(USER_A))).status_code == 422


# M1 -- one failover notice, not one per call while the primary key is cooling down.
async def test_m1_a_failover_is_announced_once_not_on_every_call(client, env):
    seed_key(env, USER_A, "gemini", "primary", "primary-key")
    seed_key(env, USER_A, "gemini", "backup", "backup-key")
    env.gemini.rate_limited_keys.add("primary-key")
    conv = (await client.post("/chat/conversations", json={"title": "t"}, headers=as_user(USER_A))).json()["id"]
    from app.llm.keystate import cooldowns, key_hash

    for i in range(4):
        r = await client.post(f"/chat/conversations/{conv}/messages",
                              json={"provider": "gemini", "content": f"hi {i}"}, headers=as_user(USER_A))
        assert r.status_code == 200
        if i == 0:  # a daily-quota style exhaustion: the key is known to be spent until reset
            cooldowns.set("gemini", key_hash("primary-key"), 3600)
    assert len(env.db.rows("notifications", user_id=USER_A)) == 1  # the first call only


# M5 -- a finished review keeps its use of the single submit, whatever happens after.
async def test_m5_a_failure_after_the_review_finished_does_not_free_the_submit(client, env, monkeypatch):
    from app.coding import service as coding_service

    seed_key(env, USER_A, "gemini", "primary", "gem")
    resume = seed_processed_resume(env, USER_A)
    q = env.db.seed("question_bank", type="coding", question="Two sum", solution_code="def f(): ...", embedding=[0.1])
    iv = env.db.seed("interviews", user_id=USER_A, type="coding", jd_text="x", resume_id=resume["id"], status="in_progress",
                     phase="problem_1", started_at=_ago(minutes=10), ends_at=_ago(minutes=-50), provider="gemini",
                     selected_question_ids=[q["id"]])
    verdict = {"trace": "For [2,7] target 9 returns [0,1] at line 3; for [] returns [] at line 5.",
               "approach": "same_as_reference", "result": "correct", "interviewer_message": "Thanks. What is the complexity?"}
    env.gemini.script = [json.dumps(verdict)]

    async def broken(*a, **k):
        raise RuntimeError("database hiccup")

    monkeypatch.setattr(coding_service.interviews_repo, "append_turns", broken)
    r = await client.post(f"/interviews/{iv['id']}/submissions", json={"language": "Python", "code": "def f(): return 1"},
                          headers=as_user(USER_A))
    await background.drain()
    job = (await client.get(f"/jobs/{r.json()['job_id']}", headers=as_user(USER_A))).json()
    assert job["status"] == "failed" and job["error"]["code"] == "reply_not_saved"
    sub = env.db.rows("code_submissions", interview_id=iv["id"])[0]
    assert sub["status"] == "done" and sub["verdict"]["result"] == "correct"  # not flipped to failed
    again = await client.post(f"/interviews/{iv['id']}/submissions", json={"language": "Python", "code": "def f(): return 2"},
                              headers=as_user(USER_A))
    assert again.status_code == 409 and again.json()["error"]["code"] == "already_submitted"


async def test_m5_boot_recovery_does_not_touch_a_finished_review(env):
    from app.main import _recover_jobs

    resume = seed_processed_resume(env, USER_A)
    iv = env.db.seed("interviews", user_id=USER_A, type="coding", jd_text="x", resume_id=resume["id"], status="in_progress")
    q = env.db.seed("question_bank", type="coding", question="q", embedding=[0.1])
    sub = env.db.seed("code_submissions", interview_id=iv["id"], user_id=USER_A, question_id=q["id"], language="Python",
                      code="x", line_count=1, status="done", verdict={"result": "correct"})
    env.db.seed("jobs", user_id=USER_A, kind="code_review", status="running", subject_id=sub["id"])
    await _recover_jobs()
    assert env.db.rows("code_submissions", id=sub["id"])[0]["status"] == "done"


# M6 -- validating a key never ends in a raw 500.
@pytest.mark.parametrize(
    "error, status, code",
    [
        (ProviderTimeoutError("slow"), 504, "provider_timeout"),
        (ProviderAuthError("403 no access"), 400, "key_rejected"),
        (RuntimeError("some SDK exploded"), 502, "provider_error"),
    ],
)
async def test_m6_key_validation_failures_are_clean_errors(client, env, error, status, code):
    env.gemini.validate_error = error
    r = await client.post("/keys", json={"provider": "gemini", "slot": "primary", "api_key": "AIza-secret-key-0123456789"}, headers=as_user(USER_A))
    assert r.status_code == status and r.json()["error"]["code"] == code
    assert env.db.rows("provider_keys") == []  # nothing saved
    assert "SDK exploded" not in r.text


# M4 -- a long question must not push the conversation out of the turn prompt.
def test_m4_the_history_keeps_its_minimum_room_even_with_a_huge_system_prompt_and_context():
    system = Message(role=MessageRole.SYSTEM, content="rules " * 400)  # ~600 tokens incl. a 400-token question
    last_ai = Message(role=MessageRole.ASSISTANT, content="What is the time complexity of your approach? " * 3)
    answer = Message(role=MessageRole.USER, content="word " * 480)  # a full-length spoken answer (~600 tokens)
    context_tokens = 650
    fixed = estimate_messages_tokens([system]) + context_tokens
    budget = max(_PROMPT_BUDGET_TOKENS, fixed + _MIN_HISTORY_TOKENS)
    fitted = fit_to_budget([system, last_ai, answer], budget, keep_leading=1)
    assert fitted[1].content == last_ai.content  # the interviewer's own last question survives
    assert len(fitted[-1].content) > 1800  # and so does (nearly all of) the answer


# L8 / M2 are covered where they live (test_reports_flow, test_jobs_flow).
