"""Runs long work as a background job the page can poll.

`launch()` records a job row and starts the work on the event loop; the work
reports short progress lines; the outcome (result or a typed error) is written
back to the row, and the UI reads it with GET /jobs/{id}. At most
MAX_CONCURRENT jobs run at once -- the rest wait as "queued" -- so a burst
cannot starve ordinary requests.

Jobs live in this process (like the limiter and the background tasks). If the
process dies, startup recovery (`recover_interrupted`) marks the orphans failed
so a user is never stuck behind a job nobody is running.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from fastapi import HTTPException

from app.core import background
from app.core.errors import code_for
from app.db import jobs as jobs_repo

logger = logging.getLogger(__name__)

MAX_CONCURRENT = 6  # the work is I/O-bound on each user's own provider key
# A running job proves it is alive with a heartbeat every HEARTBEAT_SECONDS, so
# a few missed beats mean its process is gone (crash, restart, lost write). A
# job still waiting for a slot has no heartbeat and is judged by its age.
HEARTBEAT_SECONDS = 20
STALE_RUNNING_SECONDS = 90
STALE_QUEUED_SECONDS = 420

Reporter = Callable[[str], Awaitable[None]]
Work = Callable[[Reporter], Awaitable[dict]]
OnFailure = Callable[[], Awaitable[None]]

_slots: asyncio.Semaphore | None = None


def _semaphore() -> asyncio.Semaphore:
    global _slots
    if _slots is None:
        _slots = asyncio.Semaphore(MAX_CONCURRENT)
    return _slots


def reset() -> None:
    """Forget the semaphore (tests run each on a fresh event loop)."""
    global _slots
    _slots = None


def is_stale(job: dict, now: datetime | None = None) -> bool:
    running = job.get("status") == "running"
    seen = (job.get("heartbeat_at") or job.get("started_at") or job.get("created_at")) if running else job.get("created_at")
    if not seen:
        return True
    when = datetime.fromisoformat(str(seen).replace("Z", "+00:00"))
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    limit = STALE_RUNNING_SECONDS if running else STALE_QUEUED_SECONDS
    return ((now or datetime.now(UTC)) - when).total_seconds() > limit


async def _heartbeat(job_id: str) -> None:
    while True:
        await asyncio.sleep(HEARTBEAT_SECONDS)
        await _safe(jobs_repo.touch, job_id)


async def _safe(coro_fn, *args) -> None:
    """Progress and bookkeeping writes must never kill the job itself."""
    try:
        await coro_fn(*args)
    except Exception:
        logger.warning("Job bookkeeping write failed", exc_info=True)


async def _run(job_id: str, work: Work, on_failure: OnFailure | None) -> None:
    async with _semaphore():
        try:
            started = await jobs_repo.mark_started(job_id)
        except Exception:
            logger.warning("Could not mark job %s started", job_id, exc_info=True)
            started = True  # bookkeeping trouble must not cancel the user's work
        if not started:
            logger.info("Job %s is no longer queued (failed while waiting); skipped", job_id)
            return

        async def report(text: str) -> None:
            await _safe(jobs_repo.mark_progress, job_id, text)

        beat = asyncio.get_running_loop().create_task(_heartbeat(job_id), name=f"heartbeat:{job_id}")
        try:
            result = await work(report)
        except HTTPException as exc:
            error = {"code": code_for(exc), "message": str(exc.detail), "status": exc.status_code}
        except Exception:
            logger.exception("Job %s crashed", job_id)
            error = {
                "code": "internal_error",
                "message": "Something went wrong on our side -- please try again.",
                "status": 500,
            }
        else:
            beat.cancel()
            await _safe(jobs_repo.mark_succeeded, job_id, result)
            return
        finally:
            beat.cancel()

        await _safe(jobs_repo.mark_failed, job_id, error)
        if on_failure is not None:
            await _safe(on_failure)


async def launch(
    user_id: str,
    kind: str,
    subject_id: str | None,
    work: Work,
    on_failure: OnFailure | None = None,
    on_stale: Callable[[dict], Awaitable[None]] | None = None,
) -> tuple[dict, bool]:
    """Starts `work` as a job. Returns (job_row, created). If the user already
    has an active job of this kind, nothing is started and that job is
    returned with created=False -- unless it has shown no sign of life for
    STALE_AFTER_SECONDS (its process is gone, or a status write was lost): it
    is then failed, `on_stale` tidies whatever it was about, and a fresh job
    starts, so one stuck row can never block a feature until the next restart."""
    job = None
    for _ in range(3):
        job = await jobs_repo.create_job(user_id, kind, subject_id)
        if job is not None:
            break
        existing = await jobs_repo.active_job(user_id, kind)
        if existing is None:
            continue  # it finished between the two calls: try again
        if not is_stale(existing):
            return existing, False
        await fail_stale(existing, "The previous attempt stopped responding -- please try again.")
        if on_stale is not None:
            await _safe(on_stale, existing)
    if job is None:
        raise RuntimeError("could not create job")
    background.schedule(_run(job["id"], work, on_failure), name=f"job:{job['id']}")
    return job, True


async def fail_stale(job: dict, message: str) -> None:
    await jobs_repo.mark_failed(
        job["id"], {"code": "interrupted", "message": message, "status": 503}
    )
