"""Interview lifecycle end to end: start -> turns -> complete -> transcript."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from app.core import background

from app.providers.base import ProviderBlockedError, ProviderUnavailableError

from .conftest import USER_A, USER_B, as_user, new_id, seed_key, seed_processed_resume


def _ago(minutes: float) -> str:
    return (datetime.now(UTC) - timedelta(minutes=minutes)).isoformat()


def _seed_questions(env, n=2, type_="coding"):
    return [
        env.db.seed("question_bank", type=type_, question=f"Question {i}: reverse a linked list",
                    embedding=[0.1, 0.2, 0.3])
        for i in range(n)
    ]


class _Outcome:
    """What a caller of the old synchronous start saw, rebuilt from the job."""

    def __init__(self, status_code, body):
        self.status_code, self._body = status_code, body

    def json(self):
        return self._body


async def _start(client, env, user=USER_A, type_="coding", provider="gemini", jd="Senior Python role"):
    """Starts an interview and waits for its setup job. Returns the interview
    (status 200) when the job succeeded, the job's error when it failed, or the
    immediate refusal (404/412/422) when the request was rejected up front."""
    resume = seed_processed_resume(env, user)
    r = await client.post(
        "/interviews",
        json={"type": type_, "provider": provider, "resume_id": resume["id"], "jd_text": jd},
        headers=as_user(user),
    )
    if r.status_code != 202:
        return r, resume
    await background.drain()
    started = r.json()
    job = (await client.get(f"/jobs/{started['job_id']}", headers=as_user(user))).json()
    if job["status"] == "failed":
        return _Outcome(job["error"]["status"], {"error": job["error"], "detail": job["error"]["message"]}), resume
    assert job["status"] == "succeeded", job
    return await client.get(f"/interviews/{started['interview_id']}", headers=as_user(user)), resume


@pytest.fixture
def keyed(env):
    seed_key(env, USER_A, "gemini", "primary", "gem-a")
    seed_key(env, USER_B, "gemini", "primary", "gem-b")
    return env


# ------------------------------- start -------------------------------


async def test_start_interview_sets_up_and_flips_to_in_progress(client, keyed):
    questions = _seed_questions(keyed)
    r, resume = await _start(client, keyed)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "in_progress" and body["phase"] == "intro"
    assert body["provider"] == "gemini" and body["resume_id"] == resume["id"]
    assert body["started_at"] and body["ends_at"]
    assert set(body) == {"id", "type", "status", "phase", "provider", "resume_id",
                         "started_at", "ends_at", "created_at"}  # no jd_text / brief leak

    row = keyed.db.rows("interviews", id=body["id"])[0]
    assert row["brief"] == "Senior Python role needing Kubernetes."
    assert set(row["selected_question_ids"]) == {q["id"] for q in questions}
    ends = datetime.fromisoformat(row["ends_at"]) - datetime.fromisoformat(row["started_at"])
    assert ends == timedelta(minutes=60)

    transcript = keyed.db.rows("interview_transcripts", interview_id=body["id"])
    assert [(t["turn_index"], t["speaker"]) for t in transcript] == [(0, "ai")]
    assert "Welcome" in transcript[0]["text"]
    # setup = 1 batched embed + 1 JSON-mode LLM call
    assert len(keyed.gemini.embed_calls) == 1
    assert [(c.options.task, c.options.json_mode) for c in keyed.gemini.chat_calls] == [("interview", True)]


async def test_start_rejects_other_users_resume_unprocessed_resume_and_missing_key(client, keyed, env):
    other = seed_processed_resume(env, USER_B)
    r = await client.post(
        "/interviews",
        json={"type": "hr", "provider": "gemini", "resume_id": other["id"], "jd_text": "A short job description"},
        headers=as_user(USER_A),
    )
    assert r.status_code == 404

    raw = env.db.seed("resumes", user_id=USER_A, file_key="k.pdf")
    r = await client.post(
        "/interviews",
        json={"type": "hr", "provider": "gemini", "resume_id": raw["id"], "jd_text": "A short job description"},
        headers=as_user(USER_A),
    )
    assert r.status_code == 422

    env.db.tables["provider_keys"] = [k for k in env.db.tables["provider_keys"] if k["user_id"] != USER_A]
    mine = seed_processed_resume(env, USER_A)
    r = await client.post(
        "/interviews",
        json={"type": "hr", "provider": "gemini", "resume_id": mine["id"], "jd_text": "A short job description"},
        headers=as_user(USER_A),
    )
    assert r.status_code == 412
    assert env.db.rows("interviews") == []  # failed fast, before a row was created


async def test_claude_and_unknown_types_are_rejected_by_validation(client, keyed):
    resume = seed_processed_resume(keyed, USER_A)
    for patch in ({"provider": "claude"}, {"type": "astrology"}):
        body = {"type": "hr", "provider": "gemini", "resume_id": resume["id"], "jd_text": "A short job description", **patch}
        r = await client.post("/interviews", json=body, headers=as_user(USER_A))
        assert r.status_code == 422


async def test_groq_interview_uses_groq_for_chat_and_gemini_for_embeddings(client, env):
    seed_key(env, USER_A, "gemini", "primary", "gem-a")
    seed_key(env, USER_A, "groq", "primary", "groq-a")
    _seed_questions(env, 2, "coding")  # a type that needs questions, so setup embeds the JD
    r, _ = await _start(client, env, provider="groq", type_="coding")
    assert r.status_code == 200
    assert env.groq.chat_calls and not env.gemini.chat_calls
    assert env.gemini.embed_calls and env.gemini.embed_calls[0].api_key == "gem-a"  # embeddings stay on Gemini
    assert env.gemini.embed_calls[0].kind == "query"


async def test_setup_failure_marks_interview_aborted_and_returns_clean_error(client, keyed):
    keyed.gemini.script = [ProviderBlockedError("safety")]
    r, _ = await _start(client, keyed)
    assert r.status_code == 422
    rows = keyed.db.rows("interviews", user_id=USER_A)
    assert [x["status"] for x in rows] == ["aborted"]


async def test_setup_repairs_truncated_json_with_one_more_try(client, keyed):
    keyed.gemini.script = ['{"brief": "short", "opening": "Hello there, tell me about yourse']
    r, _ = await _start(client, keyed)
    assert r.status_code == 200
    text = keyed.db.rows("interview_transcripts", interview_id=r.json()["id"])[0]["text"]
    assert not text.lstrip().startswith("{") and text  # the repair reply was valid
    assert len(keyed.gemini.chat_calls) == 2  # first attempt + exactly one repair


async def test_setup_never_shows_raw_json_even_when_the_repair_fails_too(client, keyed):
    broken = '{"brief": "short", "opening": "Hello there, tell me about yourse'
    keyed.gemini.script = [broken, "still not json at all"]
    r, _ = await _start(client, keyed)
    assert r.status_code == 200
    text = keyed.db.rows("interview_transcripts", interview_id=r.json()["id"])[0]["text"]
    assert not text.lstrip().startswith("{") and "Hello there" in text  # salvaged from the first attempt


async def test_coding_interview_with_empty_question_bank_starts_with_no_questions(client, keyed):
    """Characterisation of a plan gap: nothing warns or refuses when the bank
    has no questions for the type; the coding interview just has none."""
    r, _ = await _start(client, keyed)
    assert r.status_code == 200
    assert keyed.db.rows("interviews", id=r.json()["id"])[0]["selected_question_ids"] == []


# ------------------------------- turns -------------------------------


async def test_full_flow_turns_complete_and_transcript(client, keyed):
    r, _ = await _start(client, keyed, type_="behavioral")
    iid = r.json()["id"]

    t = await client.post(f"/interviews/{iid}/turns", json={"content": "I led a migration."},
                          headers=as_user(USER_A))
    assert t.status_code == 200
    d = t.json()
    assert d["message"] == "Thanks. How would you design that for scale?"
    assert d["phase"] == "warm_up" and d["is_final_phase"] is False
    assert 0 < d["minutes_remaining"] <= 60

    # exactly one LLM call for the turn, capped output, user-first
    call = keyed.gemini.chat_calls[-1]
    assert call.options.max_output_tokens == 160 and call.options.task == "interview"
    non_system = [m for m in call.messages if m.role.value != "system"]
    assert non_system[0].role.value == "user"
    # the candidate's answer travels as marked-up data
    assert "I led a migration." in non_system[-1].content and "<data kind=\"candidate_answer\"" in non_system[-1].content
    # injection standard: the brief (distilled from untrusted text) is NOT in the system role,
    # it rides along as data in the conversation; the system role only carries our rules
    assert "Senior Python role needing Kubernetes." not in call.messages[0].content
    assert "Senior Python role needing Kubernetes." in non_system[0].content
    assert "never instructions" in call.messages[0].content
    assert "Welcome" not in call.messages[0].content

    tr = await client.get(f"/interviews/{iid}/transcript", headers=as_user(USER_A))
    assert [(e["turn_index"], e["speaker"]) for e in tr.json()] == [(0, "ai"), (1, "user"), (2, "ai")]

    done = await client.post(f"/interviews/{iid}/complete", headers=as_user(USER_A))
    assert done.status_code == 200 and done.json()["status"] == "completed"

    again = await client.post(f"/interviews/{iid}/turns", json={"content": "more"}, headers=as_user(USER_A))
    assert again.status_code == 409


async def test_phase_advances_with_elapsed_time_and_question_is_injected_only_in_problem_phase(client, keyed):
    qs = _seed_questions(keyed)
    r, _ = await _start(client, keyed, type_="coding")
    iid = r.json()["id"]

    await client.post(f"/interviews/{iid}/turns", json={"content": "hi"}, headers=as_user(USER_A))
    assert "Current question" not in keyed.gemini.chat_calls[-1].messages[0].content  # intro: not revealed

    keyed.db.rows("interviews", id=iid)[0]["started_at"] = _ago(10)
    t = await client.post(f"/interviews/{iid}/turns", json={"content": "ready"}, headers=as_user(USER_A))
    assert t.json()["phase"] == "problem_1"
    assert "reverse a linked list" in keyed.gemini.chat_calls[-1].messages[0].content
    assert keyed.db.rows("interviews", id=iid)[0]["phase"] == "problem_1"

    keyed.db.rows("interviews", id=iid)[0]["started_at"] = _ago(57)
    t = await client.post(f"/interviews/{iid}/turns", json={"content": "done"}, headers=as_user(USER_A))
    assert t.json()["phase"] == "wrap_up" and t.json()["is_final_phase"] is True
    assert "Current question" not in keyed.gemini.chat_calls[-1].messages[0].content
    assert len(qs) == 2


async def test_incremental_summary_kicks_in_after_enough_turns_and_feeds_next_prompt(client, keyed):
    r, _ = await _start(client, keyed, type_="behavioral")
    iid = r.json()["id"]
    for i in range(4):  # 1 opening + 4*2 = 9 transcript rows >= 8 new turns
        t = await client.post(f"/interviews/{iid}/turns", json={"content": f"answer {i}"},
                              headers=as_user(USER_A))
        assert t.status_code == 200
    await background.drain()  # the summary is housekeeping that runs after the reply
    tasks = [c.options.task for c in keyed.gemini.chat_calls]
    assert tasks.count("summarize") == 1
    row = keyed.db.rows("interviews", id=iid)[0]
    assert row["running_summary"] == "Covered Python; candidate was solid."
    assert row["summarized_through_turn"] == 9

    await client.post(f"/interviews/{iid}/turns", json={"content": "next"}, headers=as_user(USER_A))
    last = keyed.gemini.chat_calls[-1].messages
    # the running summary is data inside the conversation, never part of the system role
    assert any("Covered Python; candidate was solid." in m.content for m in last if m.role.value == "user")
    assert not any("Covered Python" in m.content for m in last if m.role.value == "system")


async def test_summary_failure_does_not_fail_the_turn(client, keyed):
    r, _ = await _start(client, keyed, type_="behavioral")
    iid = r.json()["id"]
    for i in range(3):
        await client.post(f"/interviews/{iid}/turns", json={"content": f"a{i}"}, headers=as_user(USER_A))
    keyed.gemini.script = ["Reply for turn 4", ProviderBlockedError("summary blocked")]
    t = await client.post(f"/interviews/{iid}/turns", json={"content": "a3"}, headers=as_user(USER_A))
    assert t.status_code == 200 and t.json()["message"] == "Reply for turn 4"
    assert keyed.db.rows("interviews", id=iid)[0]["running_summary"] is None


async def test_turn_validation_empty_and_over_4000_chars(client, keyed):
    r, _ = await _start(client, keyed, type_="hr")
    iid = r.json()["id"]
    for content in ("", "x" * 4001):
        t = await client.post(f"/interviews/{iid}/turns", json={"content": content}, headers=as_user(USER_A))
        assert t.status_code == 422


async def test_quota_exhaustion_mid_interview_fails_over_to_backup_key(client, keyed):
    seed_key(keyed, USER_A, "gemini", "backup", "gem-a-backup")
    r, _ = await _start(client, keyed, type_="hr")
    iid = r.json()["id"]
    keyed.gemini.rate_limited_keys.add("gem-a")
    t = await client.post(f"/interviews/{iid}/turns", json={"content": "hello"}, headers=as_user(USER_A))
    assert t.status_code == 200
    assert keyed.gemini.chat_calls[-1].api_key == "gem-a-backup"
    assert keyed.db.rows("notifications", user_id=USER_A)


# ---------------------------- ownership ----------------------------


async def test_other_users_cannot_read_or_drive_my_interview(client, keyed):
    r, _ = await _start(client, keyed, type_="hr")
    iid = r.json()["id"]
    h = as_user(USER_B)
    assert (await client.get(f"/interviews/{iid}", headers=h)).status_code == 404
    assert (await client.get(f"/interviews/{iid}/transcript", headers=h)).status_code == 404
    assert (await client.post(f"/interviews/{iid}/turns", json={"content": "hi"}, headers=h)).status_code == 404
    assert (await client.post(f"/interviews/{iid}/complete", headers=h)).status_code == 404
    assert keyed.db.rows("interviews", id=iid)[0]["status"] == "in_progress"
    assert (await client.get("/interviews", headers=h)).json() == []
    assert [i["id"] for i in (await client.get("/interviews", headers=as_user(USER_A))).json()] == [iid]


async def test_unknown_interview_is_404(client, keyed):
    assert (await client.get(f"/interviews/{new_id()}", headers=as_user(USER_A))).status_code == 404


# --------------------------- question bank ---------------------------

OWNER = "33333333-3333-3333-3333-333333333333"
ADMIN_OK = "44444444-4444-4444-4444-444444444444"
ADMIN_NO = "55555555-5555-5555-5555-555555555555"
PLAIN = USER_A


@pytest.fixture
def staffed(env):
    env.db.seed("roles", user_id=OWNER, role="owner")
    env.db.seed("roles", user_id=ADMIN_OK, role="admin")
    env.db.seed("roles", user_id=ADMIN_NO, role="admin")
    env.db.seed("roles", user_id=PLAIN, role="user")
    env.db.seed("admin_permissions", admin_id=ADMIN_OK, permission_key="manage_question_bank")
    env.db.seed("admin_permissions", admin_id=ADMIN_NO, permission_key="manage_users")
    for u in (OWNER, ADMIN_OK, ADMIN_NO, PLAIN):
        seed_key(env, u, "gemini", "primary", f"k-{u[:2]}")
    return env


TWO_SUM_SOLUTION = """def f(a, t):
    seen = {}
    for i, x in enumerate(a):
        if t - x in seen:
            return [seen[t - x], i]
        seen[x] = i
"""
QUESTION = {"type": "coding", "question": "Two sum", "solution_code": TWO_SUM_SOLUTION,
            "solution_language": "Python", "tags": ["arrays"]}


@pytest.mark.parametrize("user,expected", [(OWNER, 201), (ADMIN_OK, 201), (ADMIN_NO, 403), (PLAIN, 403)])
async def test_create_question_permission_matrix(client, staffed, user, expected):
    r = await client.post("/interviews/question-bank", json=QUESTION, headers=as_user(user))
    assert r.status_code == expected
    created = staffed.db.rows("question_bank")
    assert len(created) == (1 if expected == 201 else 0)
    if expected == 201:
        assert created[0]["embedding"] and created[0]["created_by"] == user
        assert r.json()["question"] == "Two sum" and "embedding" not in r.json()


async def test_question_bank_requires_authentication(client, staffed):
    for method, path in (("POST", "/interviews/question-bank"), ("GET", "/interviews/question-bank")):
        assert (await client.request(method, path, json=QUESTION)).status_code == 401


async def test_user_without_any_role_row_is_forbidden(client, staffed):
    seed_key(staffed, USER_B, "gemini", "primary", "k")
    r = await client.post("/interviews/question-bank", json=QUESTION, headers=as_user(USER_B))
    assert r.status_code == 403


async def test_update_and_delete_permission_matrix_and_reembedding(client, staffed):
    q = staffed.db.seed("question_bank", type="coding", question="old", embedding=[9, 9, 9])
    for user in (PLAIN, ADMIN_NO):
        assert (await client.patch(f"/interviews/question-bank/{q['id']}", json={"question": "hax"},
                                   headers=as_user(user))).status_code == 403
        assert (await client.delete(f"/interviews/question-bank/{q['id']}",
                                    headers=as_user(user))).status_code == 403
    assert staffed.db.rows("question_bank", id=q["id"])[0]["question"] == "old"

    r = await client.patch(f"/interviews/question-bank/{q['id']}", json={"question": "new"},
                           headers=as_user(ADMIN_OK))
    assert r.status_code == 200 and r.json()["question"] == "new"
    assert staffed.db.rows("question_bank", id=q["id"])[0]["embedding"] == [0.1, 0.2, 0.3]

    assert (await client.patch(f"/interviews/question-bank/{new_id()}", json={"question": "x"},
                               headers=as_user(OWNER))).status_code == 404
    assert (await client.delete(f"/interviews/question-bank/{q['id']}", headers=as_user(OWNER))).status_code == 204
    assert staffed.db.rows("question_bank") == []


async def test_question_list_is_limited_to_bank_managers_and_route_is_not_shadowed(client, staffed):
    staffed.db.seed("question_bank", type="coding", question="c1")
    staffed.db.seed("question_bank", type="hr", question="h1")
    for user in (OWNER, ADMIN_OK):
        r = await client.get("/interviews/question-bank", headers=as_user(user))
        assert r.status_code == 200 and len(r.json()) == 2  # not swallowed by /{interview_id}
    r = await client.get("/interviews/question-bank?type=hr", headers=as_user(OWNER))
    assert [q["question"] for q in r.json()] == ["h1"]
    for user in (PLAIN, ADMIN_NO):  # test cases are the answer key
        assert (await client.get("/interviews/question-bank", headers=as_user(user))).status_code == 403


async def test_question_creation_needs_the_callers_own_gemini_key(client, staffed):
    staffed.db.tables["provider_keys"] = [k for k in staffed.db.tables["provider_keys"] if k["user_id"] != OWNER]
    r = await client.post("/interviews/question-bank", json=QUESTION, headers=as_user(OWNER))
    assert r.status_code == 412


async def test_question_bank_type_is_validated(client, staffed):
    r = await client.post("/interviews/question-bank", json={**QUESTION, "type": "nope"}, headers=as_user(OWNER))
    assert r.status_code == 422


# --------------------------- findings ---------------------------


async def test_turn_after_the_hour_is_over_is_refused(client, keyed):
    r, _ = await _start(client, keyed, type_="hr")
    iid = r.json()["id"]
    keyed.db.rows("interviews", id=iid)[0]["started_at"] = _ago(180)
    t = await client.post(f"/interviews/{iid}/turns", json={"content": "still here"}, headers=as_user(USER_A))
    assert t.status_code in (409, 410)


async def test_a_double_click_gets_one_answer_and_a_clear_409(client, keyed):
    """The second concurrent answer is refused (no second LLM call, no turn-slot race)."""
    r, _ = await _start(client, keyed, type_="hr")
    iid = r.json()["id"]
    keyed.db.select_delay["interviews"] = 0.05
    results = await asyncio.gather(*[
        client.post(f"/interviews/{iid}/turns", json={"content": f"dbl {i}"}, headers=as_user(USER_A))
        for i in range(2)
    ])
    codes = sorted(x.status_code for x in results)
    assert codes == [200, 409], codes
    assert [x for x in results if x.status_code == 409][0].json()["error"]["code"] == "turn_in_progress"
    idx = [t["turn_index"] for t in keyed.db.rows("interview_transcripts", interview_id=iid)]
    assert len(idx) == len(set(idx)), idx


async def test_the_answer_and_the_reply_are_stored_together_with_consecutive_indexes(client, keyed):
    r, _ = await _start(client, keyed, type_="hr")
    iid = r.json()["id"]
    await client.post(f"/interviews/{iid}/turns", json={"content": "first"}, headers=as_user(USER_A))
    await client.post(f"/interviews/{iid}/turns", json={"content": "second"}, headers=as_user(USER_A))
    rows = sorted(keyed.db.rows("interview_transcripts", interview_id=iid), key=lambda t: t["turn_index"])
    assert [t["turn_index"] for t in rows] == [0, 1, 2, 3, 4]
    assert [t["speaker"] for t in rows] == ["ai", "user", "ai", "user", "ai"]
    assert [n for n, _ in keyed.db.rpc_calls].count("append_interview_turns") == 2


async def test_failed_turn_leaves_no_dangling_user_answer(client, keyed):
    r, _ = await _start(client, keyed, type_="hr")
    iid = r.json()["id"]
    keyed.gemini.script = [ProviderUnavailableError("x")] * 3
    t = await client.post(f"/interviews/{iid}/turns", json={"content": "my answer"}, headers=as_user(USER_A))
    assert t.status_code == 503
    speakers = [e["speaker"] for e in keyed.db.rows("interview_transcripts", interview_id=iid)]
    assert speakers == ["ai"]


async def test_retry_after_failed_turn_does_not_duplicate_the_answer(client, keyed):
    """CONFIRMED consequence of the bug above."""
    r, _ = await _start(client, keyed, type_="hr")
    iid = r.json()["id"]
    keyed.gemini.script = [ProviderBlockedError("x")]
    await client.post(f"/interviews/{iid}/turns", json={"content": "my answer"}, headers=as_user(USER_A))
    await client.post(f"/interviews/{iid}/turns", json={"content": "my answer"}, headers=as_user(USER_A))
    texts = [(e["speaker"], e["text"]) for e in
             sorted(keyed.db.rows("interview_transcripts", interview_id=iid), key=lambda e: e["turn_index"])]
    assert texts.count(("user", "my answer")) == 1  # the failed attempt saved nothing


async def test_cannot_complete_an_aborted_interview(client, keyed):
    resume = seed_processed_resume(keyed, USER_A)
    row = keyed.db.seed("interviews", user_id=USER_A, type="hr", jd_text="jd", resume_id=resume["id"],
                        status="aborted")
    r = await client.post(f"/interviews/{row['id']}/complete", headers=as_user(USER_A))
    assert r.status_code == 409


async def test_empty_or_giant_jd_rejected_on_start(client, keyed):
    resume = seed_processed_resume(keyed, USER_A)
    for jd in ("", "x" * 3_000_000):
        r = await client.post(
            "/interviews",
            json={"type": "hr", "provider": "gemini", "resume_id": resume["id"], "jd_text": jd},
            headers=as_user(USER_A),
        )
        assert r.status_code == 422


async def test_empty_patch_body_is_not_a_500(client, staffed):
    q = staffed.db.seed("question_bank", type="coding", question="old")
    r = await client.patch(f"/interviews/question-bank/{q['id']}", json={}, headers=as_user(OWNER))
    assert r.status_code < 500


async def test_bad_filter_and_bad_ids_are_clean_4xx(client, staffed):
    r1 = await client.get("/interviews/question-bank?type=bogus", headers=as_user(OWNER))
    r2 = await client.get("/interviews/not-a-uuid", headers=as_user(PLAIN))
    assert r1.status_code < 500 and r2.status_code < 500


async def test_duplicate_permission_grant_does_not_break_the_admin(client, staffed):
    staffed.db.seed("admin_permissions", admin_id=ADMIN_OK, permission_key="manage_question_bank")
    r = await client.post("/interviews/question-bank", json=QUESTION, headers=as_user(ADMIN_OK))
    assert r.status_code == 201


async def test_empty_question_text_rejected(client, staffed):
    r = await client.post("/interviews/question-bank", json={**QUESTION, "question": ""}, headers=as_user(OWNER))
    assert r.status_code == 422
