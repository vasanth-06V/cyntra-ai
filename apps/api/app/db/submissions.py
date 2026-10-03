from postgrest.exceptions import APIError

from app.core.db import get_supabase
from app.db.base import run


async def create_submission(
    interview_id: str, user_id: str, question_id: str, language: str, code: str
) -> dict | None:
    """Claims the single submission for this problem. Returns None when one
    already exists (the partial unique index), so a double-click or a second
    attempt is refused cleanly."""
    supabase = get_supabase()

    def _q():
        return (
            supabase.table("code_submissions")
            .insert(
                {
                    "interview_id": interview_id,
                    "user_id": user_id,
                    "question_id": question_id,
                    "language": language,
                    "code": code,
                    "line_count": max(1, len(code.splitlines())),
                }
            )
            .execute()
        )

    try:
        return (await run(_q)).data[0]
    except APIError as exc:
        if getattr(exc, "code", None) == "23505":
            return None
        raise


async def get_for_question(interview_id: str, question_id: str) -> dict | None:
    """The live (non-failed) submission for a problem: language and size only,
    never the verdict."""
    supabase = get_supabase()

    def _q():
        return (
            supabase.table("code_submissions")
            .select("id, language, line_count, status, created_at")
            .eq("interview_id", interview_id)
            .eq("question_id", question_id)
            .in_("status", ["review", "done"])
            .limit(1)
            .execute()
        )

    rows = (await run(_q)).data
    return rows[0] if rows else None


async def done_summary(interview_id: str, question_id: str) -> dict | None:
    """Language and the reviewer's short summary of a finished submission,
    for the interviewer's later turns."""
    supabase = get_supabase()

    def _q():
        return (
            supabase.table("code_submissions")
            .select("language, summary")
            .eq("interview_id", interview_id)
            .eq("question_id", question_id)
            .eq("status", "done")
            .limit(1)
            .execute()
        )

    rows = (await run(_q)).data
    return rows[0] if rows else None


async def mark_done(submission_id: str, verdict: dict, summary: str) -> None:
    supabase = get_supabase()

    def _q():
        return (
            supabase.table("code_submissions")
            .update({"status": "done", "verdict": verdict, "summary": summary})
            .eq("id", submission_id)
            .execute()
        )

    await run(_q)


async def mark_failed(submission_id: str) -> None:
    """Frees the single submit -- but only while the review is still running.
    A review that already finished ('done') keeps its verdict and its use of the submit."""
    supabase = get_supabase()

    def _q():
        return (
            supabase.table("code_submissions")
            .update({"status": "failed"})
            .eq("id", submission_id)
            .eq("status", "review")
            .execute()
        )

    await run(_q)


async def finished_for_interview(interview_id: str) -> list[dict]:
    """Every finished review of this interview, with its verdict (for the report)."""
    supabase = get_supabase()

    def _q():
        return (
            supabase.table("code_submissions")
            .select("question_id, language, line_count, status, verdict, created_at")
            .eq("interview_id", interview_id)
            .eq("status", "done")
            .order("created_at")
            .execute()
        )

    return (await run(_q)).data or []
