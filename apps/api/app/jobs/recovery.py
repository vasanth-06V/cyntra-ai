"""Finds jobs nobody is running any more and tidies up what they were about.

A running job beats its heart every few seconds (core/jobs.py); a job whose
heart stopped belongs to a process that died, or whose status write was lost.
This runs once at startup and then every minute, and it only touches jobs that
are STALE -- so a second instance (or a rolling deploy's overlap) never kills
the other one's live work."""

import asyncio
import logging

from app.core import jobs as job_runner
from app.db import interviews as interviews_repo
from app.db import jobs as jobs_repo
from app.db import submissions as submissions_repo

logger = logging.getLogger(__name__)

SETUP_JOB = "interview_setup"
REVIEW_JOB = "code_review"
SWEEP_EVERY_SECONDS = 60


async def tidy_subject(job: dict) -> None:
    """Undoes the half-finished effect of a dead job."""
    subject = job.get("subject_id")
    if not subject:
        return
    if job.get("kind") == SETUP_JOB:
        # Only an interview still being set up is abandoned; one that already
        # opened must never be aborted by the cleanup of its setup job.
        await interviews_repo.update_interview_if_status(subject, {"status": "aborted"}, "setting_up")
    elif job.get("kind") == REVIEW_JOB:
        # A review that never finished must not use up the candidate's single submit.
        await submissions_repo.mark_failed(subject)


async def fail_stale_jobs() -> int:
    """Fails every stale active job and tidies its subject. Never raises."""
    failed = 0
    try:
        for job in await jobs_repo.list_active():
            if not job_runner.is_stale(job):
                continue
            await job_runner.fail_stale(job, "This stopped responding (the server restarted or lost it) -- please try again.")
            try:
                await tidy_subject(job)
            except Exception:
                logger.warning("Could not tidy after stale job %s", job.get("id"), exc_info=True)
            failed += 1
    except Exception:
        logger.warning("Could not check for stale jobs", exc_info=True)
    return failed


async def sweep_forever() -> None:
    while True:
        await asyncio.sleep(SWEEP_EVERY_SECONDS)
        await fail_stale_jobs()
