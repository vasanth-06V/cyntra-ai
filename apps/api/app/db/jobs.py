from datetime import UTC, datetime

from postgrest.exceptions import APIError

from app.core.db import get_supabase
from app.db.base import run

_COLUMNS = "id, kind, status, progress, result, error, subject_id, created_at, heartbeat_at"
ACTIVE = ["queued", "running"]


def _now() -> str:
    return datetime.now(UTC).isoformat()


async def create_job(user_id: str, kind: str, subject_id: str | None) -> dict | None:
    """Inserts a queued job. Returns None when the user already has an active
    job of this kind (the partial unique index), so the caller can return that
    one instead -- a double-click must not start the work twice."""
    supabase = get_supabase()

    def _q():
        return (
            supabase.table("jobs")
            .insert({"user_id": user_id, "kind": kind, "subject_id": subject_id})
            .execute()
        )

    try:
        return (await run(_q)).data[0]
    except APIError as exc:
        if getattr(exc, "code", None) == "23505":
            return None
        raise


async def active_job(user_id: str, kind: str) -> dict | None:
    supabase = get_supabase()

    def _q():
        return (
            supabase.table("jobs")
            .select(_COLUMNS)
            .eq("user_id", user_id)
            .eq("kind", kind)
            .in_("status", ACTIVE)
            .limit(1)
            .execute()
        )

    rows = (await run(_q)).data
    return rows[0] if rows else None


async def get_owned_job(user_id: str, job_id: str) -> dict | None:
    supabase = get_supabase()

    def _q():
        return (
            supabase.table("jobs")
            .select(_COLUMNS)
            .eq("id", job_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )

    result = await run(_q)
    return result.data if result and result.data else None


async def update_job(job_id: str, fields: dict) -> None:
    supabase = get_supabase()

    def _q():
        return supabase.table("jobs").update(fields).eq("id", job_id).execute()

    await run(_q)


async def mark_started(job_id: str) -> bool:
    """queued -> running, only if the job is still queued. False means it was
    failed in the meantime (e.g. judged stale while waiting for a slot): its
    work must not run, or it would act on state the user has moved on from."""
    supabase = get_supabase()

    def _q():
        return (
            supabase.table("jobs")
            .update({"status": "running", "started_at": _now(), "heartbeat_at": _now()})
            .eq("id", job_id)
            .eq("status", "queued")
            .execute()
        )

    return bool((await run(_q)).data)


async def mark_progress(job_id: str, text: str) -> None:
    await update_job(job_id, {"progress": text, "heartbeat_at": _now()})


async def _update_active(job_id: str, fields: dict) -> None:
    """Updates a job only while it is still queued/running: a job already failed
    (cancelled, judged stale) can never be flipped back to another state by a
    task that was slow to notice."""
    supabase = get_supabase()

    def _q():
        return supabase.table("jobs").update(fields).eq("id", job_id).in_("status", ACTIVE).execute()

    await run(_q)


async def touch(job_id: str) -> None:
    """Liveness signal: the process running this job is alive."""
    await _update_active(job_id, {"heartbeat_at": _now()})


async def mark_succeeded(job_id: str, result: dict) -> None:
    await _update_active(
        job_id, {"status": "succeeded", "result": result, "progress": None, "finished_at": _now()}
    )


async def mark_failed(job_id: str, error: dict) -> None:
    await _update_active(
        job_id, {"status": "failed", "error": error, "progress": None, "finished_at": _now()}
    )


async def list_active() -> list[dict]:
    supabase = get_supabase()

    def _q():
        return (
            supabase.table("jobs")
            .select("id, kind, status, subject_id, created_at, started_at, heartbeat_at")
            .in_("status", ACTIVE)
            .limit(500)
            .execute()
        )

    return (await run(_q)).data or []
