"""Team management, ATS history, aborting/deleting interviews, renaming chats,
clearing question fields."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from app.core import background

from .conftest import ADMIN_NO_PERM, ADMIN_WITH_PERM, OWNER, USER_A, USER_B, as_user, seed_key, seed_processed_resume


def _ago(**kw):
    return (datetime.now(UTC) - timedelta(**kw)).isoformat()


@pytest.fixture
def team(env):
    for uid, email in ((OWNER, "owner@x.com"), (ADMIN_WITH_PERM, "admin@x.com"), (USER_A, "a@x.com"), (USER_B, "b@x.com")):
        env.db.seed("profiles", id=uid, full_name=email.split("@")[0])
        env.db.tables.setdefault("auth_users", []).append({"id": uid, "email": email})
    env.db.seed("roles", user_id=OWNER, role="owner")
    env.db.seed("roles", user_id=ADMIN_WITH_PERM, role="admin")
    env.db.seed("admin_permissions", admin_id=ADMIN_WITH_PERM, permission_key="manage_question_bank")
    return env


# ------------------------------------------------------------------ team


async def test_the_owner_lists_everyone_with_roles_and_permissions(client, team):
    r = await client.get("/team/users", headers=as_user(OWNER))
    assert r.status_code == 200
    users = r.json()
    assert [u["email"] for u in users] == ["owner@x.com", "admin@x.com", "a@x.com", "b@x.com"]  # owner, admins, users
    by = {u["email"]: u for u in users}
    assert by["admin@x.com"]["role"] == "admin" and by["admin@x.com"]["permissions"] == ["manage_question_bank"]
    assert by["a@x.com"]["role"] == "user" and by["a@x.com"]["permissions"] == []


async def test_nobody_but_the_owner_can_manage_the_team(client, team):
    for user in (ADMIN_WITH_PERM, USER_A):
        assert (await client.get("/team/users", headers=as_user(user))).status_code == 403
        assert (await client.patch(f"/team/users/{USER_B}/role", json={"role": "admin"}, headers=as_user(user))).status_code == 403
        assert (await client.put(f"/team/users/{ADMIN_WITH_PERM}/permissions", json={"permissions": []}, headers=as_user(user))).status_code == 403
    assert team.db.rows("roles", user_id=USER_B) == []  # nothing changed


async def test_promote_grant_and_demote(client, team):
    up = await client.patch(f"/team/users/{USER_A}/role", json={"role": "admin"}, headers=as_user(OWNER))
    assert up.status_code == 200 and up.json() == {"id": USER_A, "role": "admin"}
    assert team.db.rows("roles", user_id=USER_A)[0]["role"] == "admin"

    granted = await client.put(f"/team/users/{USER_A}/permissions", json={"permissions": ["manage_question_bank", "manage_question_bank"]},
                               headers=as_user(OWNER))
    assert granted.json()["permissions"] == ["manage_question_bank"]  # de-duplicated
    assert [p["permission_key"] for p in team.db.rows("admin_permissions", admin_id=USER_A)] == ["manage_question_bank"]

    down = await client.patch(f"/team/users/{USER_A}/role", json={"role": "user"}, headers=as_user(OWNER))
    assert down.status_code == 200
    assert team.db.rows("admin_permissions", admin_id=USER_A) == []  # a plain user holds nothing


async def test_team_rules_and_validation(client, team):
    h = as_user(OWNER)
    assert (await client.patch(f"/team/users/{OWNER}/role", json={"role": "user"}, headers=h)).json()["error"]["code"] == "cannot_change_owner"
    assert (await client.patch(f"/team/users/{USER_A}/role", json={"role": "owner"}, headers=h)).status_code == 422  # never creates owners
    assert (await client.patch(f"/team/users/{new_uuid()}/role", json={"role": "admin"}, headers=h)).status_code == 404
    plain = await client.put(f"/team/users/{USER_B}/permissions", json={"permissions": ["manage_question_bank"]}, headers=h)
    assert plain.status_code == 422 and plain.json()["error"]["code"] == "not_an_admin"
    bad = await client.put(f"/team/users/{ADMIN_WITH_PERM}/permissions", json={"permissions": ["delete_everything"]}, headers=h)
    assert bad.status_code == 422 and "delete_everything" in bad.json()["error"]["message"]
    assert (await client.patch("/team/users/not-a-uuid/role", json={"role": "admin"}, headers=h)).status_code == 422
    # an admin's permissions can be emptied
    cleared = await client.put(f"/team/users/{ADMIN_WITH_PERM}/permissions", json={"permissions": []}, headers=h)
    assert cleared.json()["permissions"] == [] and team.db.rows("admin_permissions", admin_id=ADMIN_WITH_PERM) == []


def new_uuid():
    import uuid

    return str(uuid.uuid4())


# ------------------------------------------------------------------ ATS history


async def test_each_score_is_saved_and_listed_newest_first(client, env):
    seed_key(env, USER_A, "gemini", "primary", "gem")
    resume = seed_processed_resume(env, USER_A)
    body = {"resume_id": resume["id"], "jd_text": "Senior Python and Kubernetes engineer wanted", "provider": "gemini"}
    first = await client.post("/ats/score", json=body, headers=as_user(USER_A))
    assert first.status_code == 200 and first.json()["history_id"]
    await asyncio.sleep(0.01)
    second = await client.post("/ats/score", json=body, headers=as_user(USER_A))

    listed = (await client.get(f"/ats/history?resume_id={resume['id']}", headers=as_user(USER_A))).json()
    assert [x["id"] for x in listed] == [second.json()["history_id"], first.json()["history_id"]]
    assert listed[0]["job_title"] == "Backend Engineer" and listed[0]["provider"] == "gemini"
    assert listed[0]["jd_excerpt"].startswith("Senior Python") and "result" not in listed[0]

    detail = (await client.get(f"/ats/history/{first.json()['history_id']}", headers=as_user(USER_A))).json()
    assert detail["result"]["composite_score"] == first.json()["composite_score"]
    assert "history_id" not in detail["result"]  # the stored copy is the pure result


async def test_only_the_last_ten_per_resume_are_kept(client, env):
    seed_key(env, USER_A, "gemini", "primary", "gem")
    resume = seed_processed_resume(env, USER_A)
    other = seed_processed_resume(env, USER_A)
    from app.db import ats_history

    for i in range(13):
        await ats_history.record_score(USER_A, resume["id"], f"Job {i}", "x", "gemini", 50 + i, {"n": i})
        await asyncio.sleep(0.002)
    await ats_history.record_score(USER_A, other["id"], "Other", "x", "gemini", 70, {})
    kept = [r["job_title"] for r in env.db.rows("ats_scores", resume_id=resume["id"])]
    assert len(kept) == 10 and "Job 12" in kept and "Job 3" in kept and "Job 2" not in kept  # oldest three pruned
    assert len(env.db.rows("ats_scores", resume_id=other["id"])) == 1  # another resume is not affected


async def test_history_is_private_and_deletable(client, env):
    seed_key(env, USER_A, "gemini", "primary", "gem")
    resume = seed_processed_resume(env, USER_A)
    body = {"resume_id": resume["id"], "jd_text": "Senior Python and Kubernetes engineer wanted", "provider": "gemini"}
    sid = (await client.post("/ats/score", json=body, headers=as_user(USER_A))).json()["history_id"]
    assert (await client.get(f"/ats/history/{sid}", headers=as_user(USER_B))).status_code == 404
    assert (await client.get("/ats/history", headers=as_user(USER_B))).json() == []
    await client.delete(f"/ats/history/{sid}", headers=as_user(USER_B))  # not theirs: nothing happens
    assert len(env.db.rows("ats_scores")) == 1
    assert (await client.delete(f"/ats/history/{sid}", headers=as_user(USER_A))).status_code == 204
    assert (await client.get(f"/ats/history/{sid}", headers=as_user(USER_A))).status_code == 404


async def test_a_failure_to_save_history_never_costs_the_user_their_score(client, env):
    from postgrest.exceptions import APIError

    seed_key(env, USER_A, "gemini", "primary", "gem")
    resume = seed_processed_resume(env, USER_A)
    original = env.db.run_rpc

    def broken(name, params):
        if name == "record_ats_score":
            raise APIError({"message": "boom", "code": "XX000", "details": None, "hint": None})
        return original(name, params)

    env.db.run_rpc = broken
    r = await client.post("/ats/score", json={"resume_id": resume["id"], "jd_text": "Senior Python and Kubernetes engineer", "provider": "gemini"},
                          headers=as_user(USER_A))
    assert r.status_code == 200 and r.json()["history_id"] is None and r.json()["composite_score"] >= 0


# ------------------------------------------------------------------ interviews: abort + delete


def _setting_up(env, user=USER_A):
    resume = seed_processed_resume(env, user)
    iv = env.db.seed("interviews", user_id=user, type="hr", jd_text="x", resume_id=resume["id"], status="setting_up", provider="gemini")
    job = env.db.seed("jobs", user_id=user, kind="interview_setup", status="running", subject_id=iv["id"])
    return iv, job


async def test_a_setup_can_be_cancelled_and_the_slot_is_freed(client, env):
    iv, job = _setting_up(env)
    r = await client.post(f"/interviews/{iv['id']}/abort", headers=as_user(USER_A))
    assert r.status_code == 200 and r.json()["status"] == "aborted"
    assert env.db.rows("jobs", id=job["id"])[0]["status"] == "failed"
    assert env.db.rows("jobs", id=job["id"])[0]["error"]["code"] == "cancelled"
    again = await client.post(f"/interviews/{iv['id']}/abort", headers=as_user(USER_A))
    assert again.status_code == 200  # idempotent


async def test_only_a_setting_up_interview_can_be_cancelled_and_only_by_its_owner(client, env):
    iv, _ = _setting_up(env)
    assert (await client.post(f"/interviews/{iv['id']}/abort", headers=as_user(USER_B))).status_code == 404
    env.db.rows("interviews", id=iv["id"])[0]["status"] = "in_progress"
    r = await client.post(f"/interviews/{iv['id']}/abort", headers=as_user(USER_A))
    assert r.status_code == 409 and r.json()["error"]["code"] == "interview_not_cancellable"


async def test_a_cancelled_setup_that_finishes_anyway_does_not_come_back_to_life(client, env, monkeypatch):
    from app.interviews import service

    seed_key(env, USER_A, "gemini", "primary", "gem")
    gate = asyncio.Event()
    real = service._run_setup

    async def slow(*a, **k):
        await gate.wait()
        return await real(*a, **k)

    monkeypatch.setattr(service, "_run_setup", slow)
    resume = seed_processed_resume(env, USER_A)
    r = await client.post("/interviews", json={"type": "hr", "provider": "gemini", "resume_id": resume["id"], "jd_text": "A job description"},
                          headers=as_user(USER_A))
    iid = r.json()["interview_id"]
    assert (await client.post(f"/interviews/{iid}/abort", headers=as_user(USER_A))).json()["status"] == "aborted"
    gate.set()
    await background.drain()
    row = env.db.rows("interviews", id=iid)[0]
    assert row["status"] == "aborted"  # still cancelled
    assert env.db.rows("interview_transcripts", interview_id=iid) == []  # and no opening message was written


async def test_an_interview_can_be_deleted_by_its_owner_only(client, env):
    iv = env.db.seed("interviews", user_id=USER_A, type="hr", jd_text="x", resume_id=None, status="completed", provider="gemini")
    await client.delete(f"/interviews/{iv['id']}", headers=as_user(USER_B))
    assert len(env.db.rows("interviews")) == 1  # not theirs
    assert (await client.delete(f"/interviews/{iv['id']}", headers=as_user(USER_A))).status_code == 204
    assert env.db.rows("interviews") == []
    assert (await client.delete(f"/interviews/{iv['id']}", headers=as_user(USER_A))).status_code == 404


# ------------------------------------------------------------------ chat rename, question clear


async def test_a_conversation_can_be_renamed_by_its_owner(client, env):
    c = (await client.post("/chat/conversations", json={"title": "old"}, headers=as_user(USER_A))).json()["id"]
    r = await client.patch(f"/chat/conversations/{c}", json={"title": "  Resume tips  "}, headers=as_user(USER_A))
    assert r.status_code == 200 and r.json()["title"] == "Resume tips"
    assert (await client.patch(f"/chat/conversations/{c}", json={"title": "x"}, headers=as_user(USER_B))).status_code == 404
    assert (await client.patch(f"/chat/conversations/{c}", json={"title": ""}, headers=as_user(USER_A))).status_code == 422
    assert (await client.patch(f"/chat/conversations/{c}", json={"title": "y" * 121}, headers=as_user(USER_A))).status_code == 422


async def test_an_explicit_null_clears_topic_and_difficulty_an_omitted_field_does_not(client, env):
    seed_key(env, OWNER, "gemini", "primary", "gem-owner")
    env.db.seed("roles", user_id=OWNER, role="owner")
    made = (await client.post("/interviews/question-bank", json={"type": "behavioral", "question": "Tell me about a conflict.",
                                                                 "topic": "mediation", "difficulty": 3}, headers=as_user(OWNER))).json()
    qid = made["id"]
    kept = (await client.patch(f"/interviews/question-bank/{qid}", json={"tags": ["x"]}, headers=as_user(OWNER))).json()
    assert kept["topic"] == "mediation" and kept["difficulty"] == 3  # omitted = unchanged
    cleared = (await client.patch(f"/interviews/question-bank/{qid}", json={"topic": None, "difficulty": None}, headers=as_user(OWNER))).json()
    assert cleared["topic"] is None and cleared["difficulty"] is None
    assert env.gemini.embed_calls and "mediation" not in env.gemini.embed_calls[-1].texts[0]  # re-embedded without the topic
