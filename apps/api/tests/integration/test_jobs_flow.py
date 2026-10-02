"""Interview setup as a background job: POST returns at once, the page polls
GET /jobs/{id}; double-clicks, ownership, stale jobs and restart recovery."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from app.core import background, jobs as job_runner
from app.main import _recover_jobs
from app.providers.base import ProviderBlockedError

from .conftest import USER_A, USER_B, as_user, seed_key, seed_processed_resume


@pytest.fixture
def keyed(env):
    seed_key(env, USER_A, "gemini", "primary", "gem-a")
    seed_key(env, USER_B, "gemini", "primary", "gem-b")


def _body(resume, type_="hr"):
    return {"type": type_, "provider": "gemini", "resume_id": resume["id"], "jd_text": "Senior Python role"}


async def test_start_returns_a_job_at_once_and_the_job_succeeds(client, keyed, env):
    resume = seed_processed_resume(env, USER_A)
    r = await client.post("/interviews", json=_body(resume), headers=as_user(USER_A))
    assert r.status_code == 202
    started = r.json()
    assert set(started) == {"job_id", "interview_id"}

    await background.drain()
    job = (await client.get(f"/jobs/{started['job_id']}", headers=as_user(USER_A))).json()
    assert job["status"] == "succeeded" and job["kind"] == "interview_setup"
    assert job["result"] == {"interview_id": started["interview_id"]}
    assert job["subject_id"] == started["interview_id"] and job["error"] is None
    row = env.db.rows("interviews", id=started["interview_id"])[0]
    assert row["status"] == "in_progress"


async def test_a_double_click_starts_one_setup_not_two(client, keyed, env, monkeypatch):
    from app.interviews import service

    gate = asyncio.Event()
    real = service._run_setup
    calls = []

    async def slow_setup(*args, **kwargs):
        calls.append(1)
        await gate.wait()  # the first setup is still running when the second click arrives
        return await real(*args, **kwargs)

    monkeypatch.setattr(service, "_run_setup", slow_setup)
    resume = seed_processed_resume(env, USER_A)
    first = await client.post("/interviews", json=_body(resume), headers=as_user(USER_A))
    second = await client.post("/interviews", json=_body(resume), headers=as_user(USER_A))
    assert first.status_code == second.status_code == 202
    assert first.json() == second.json()  # the second request found the first job
    gate.set()
    await background.drain()
    assert len(env.db.rows("interviews", user_id=USER_A)) == 1
    assert len(calls) == 1 and len(env.gemini.chat_calls) == 1  # one setup, one LLM call


async def test_a_failed_setup_is_reported_with_its_error_and_the_interview_is_aborted(client, keyed, env):
    env.gemini.script = [ProviderBlockedError("safety")]
    resume = seed_processed_resume(env, USER_A)
    r = await client.post("/interviews", json=_body(resume), headers=as_user(USER_A))
    await background.drain()
    job = (await client.get(f"/jobs/{r.json()['job_id']}", headers=as_user(USER_A))).json()
    assert job["status"] == "failed" and job["error"]["code"] == "reply_blocked"
    assert job["error"]["status"] == 422 and job["result"] is None
    assert [i["status"] for i in env.db.rows("interviews", user_id=USER_A)] == ["aborted"]
    # the slot is free again: a retry is accepted and gets a new job
    again = await client.post("/interviews", json=_body(resume), headers=as_user(USER_A))
    assert again.status_code == 202 and again.json()["job_id"] != r.json()["job_id"]
    await background.drain()


async def test_jobs_belong_to_their_owner(client, keyed, env):
    resume = seed_processed_resume(env, USER_A)
    r = await client.post("/interviews", json=_body(resume), headers=as_user(USER_A))
    await background.drain()
    other = await client.get(f"/jobs/{r.json()['job_id']}", headers=as_user(USER_B))
    assert other.status_code == 404
    assert (await client.get("/jobs/not-a-uuid", headers=as_user(USER_A))).status_code == 422


async def test_refusals_that_can_be_known_up_front_create_no_job(client, env):
    resume = seed_processed_resume(env, USER_A)  # no Gemini key on file
    r = await client.post("/interviews", json=_body(resume), headers=as_user(USER_A))
    assert r.status_code == 412
    assert env.db.rows("jobs") == [] and env.db.rows("interviews") == []


async def test_a_stale_active_job_does_not_block_a_new_setup(client, keyed, env):
    resume = seed_processed_resume(env, USER_A)
    old = (datetime.now(UTC) - timedelta(minutes=20)).isoformat()
    interview = env.db.seed("interviews", user_id=USER_A, type="hr", jd_text="x", resume_id=resume["id"], status="setting_up")
    stuck = env.db.seed("jobs", user_id=USER_A, kind="interview_setup", status="running",
                        subject_id=interview["id"], created_at=old, heartbeat_at=old)
    r = await client.post("/interviews", json=_body(resume), headers=as_user(USER_A))
    assert r.status_code == 202 and r.json()["job_id"] != stuck["id"]
    await background.drain()
    assert env.db.rows("jobs", id=stuck["id"])[0]["status"] == "failed"
    assert env.db.rows("jobs", id=stuck["id"])[0]["error"]["code"] == "interrupted"
    assert env.db.rows("interviews", id=interview["id"])[0]["status"] == "aborted"


async def test_startup_recovery_fails_orphaned_jobs_and_aborts_their_interviews(env, monkeypatch):
    from app.db import jobs as jobs_repo  # noqa: F401  (uses the fake installed by the env fixture)

    resume = seed_processed_resume(env, USER_A)
    interview = env.db.seed("interviews", user_id=USER_A, type="hr", jd_text="x", resume_id=resume["id"], status="setting_up")
    job = env.db.seed("jobs", user_id=USER_A, kind="interview_setup", status="running", subject_id=interview["id"])
    done = env.db.seed("jobs", user_id=USER_B, kind="interview_setup", status="succeeded")

    await _recover_jobs()

    assert env.db.rows("jobs", id=job["id"])[0]["status"] == "failed"
    assert env.db.rows("jobs", id=job["id"])[0]["error"]["code"] == "interrupted"
    assert env.db.rows("interviews", id=interview["id"])[0]["status"] == "aborted"
    assert env.db.rows("jobs", id=done["id"])[0]["status"] == "succeeded"  # untouched


async def test_recovery_survives_a_database_error(env):
    from postgrest.exceptions import APIError

    env.db.fail_on[("jobs", "update")] = APIError({"message": "down", "code": "XX000", "details": None, "hint": None})
    await _recover_jobs()  # must not raise: the API still starts


async def test_progress_is_visible_while_running_and_cleared_when_done(env):
    gate = asyncio.Event()

    async def work(report):
        await report("Choosing questions for you...")
        await gate.wait()
        return {"ok": True}

    job, created = await job_runner.launch(USER_A, "interview_setup", None, work)
    assert created
    for _ in range(50):
        await asyncio.sleep(0.01)
        row = env.db.rows("jobs", id=job["id"])[0]
        if row["progress"]:
            break
    assert row["status"] == "running" and row["progress"] == "Choosing questions for you..."
    gate.set()
    await background.drain()
    row = env.db.rows("jobs", id=job["id"])[0]
    assert row["status"] == "succeeded" and row["progress"] is None and row["result"] == {"ok": True}


async def test_at_most_two_jobs_run_at_once_and_the_rest_wait_queued(env):
    gate = asyncio.Event()
    running = 0
    peak = 0

    async def work(report):
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await gate.wait()
        running -= 1
        return {}

    users = [f"00000000-0000-0000-0000-00000000000{i}" for i in range(1, 5)]
    jobs = [(await job_runner.launch(u, "interview_setup", None, work))[0] for u in users]
    await asyncio.sleep(0.05)
    statuses = sorted(env.db.rows("jobs", id=j["id"])[0]["status"] for j in jobs)
    assert statuses == ["queued", "queued", "running", "running"] and peak == 2
    gate.set()
    await background.drain()
    assert all(env.db.rows("jobs", id=j["id"])[0]["status"] == "succeeded" for j in jobs)


async def test_an_unexpected_crash_is_reported_generically_without_leaking_details(env):
    async def work(report):
        raise RuntimeError("secret internal detail")

    job, _ = await job_runner.launch(USER_A, "interview_setup", None, work)
    await background.drain()
    row = env.db.rows("jobs", id=job["id"])[0]
    assert row["status"] == "failed" and row["error"]["code"] == "internal_error"
    assert "secret" not in row["error"]["message"]
