from app.core.db import get_supabase
from app.db.base import run

KEEP_PER_RESUME = 10
_SUMMARY = "id, resume_id, job_title, jd_excerpt, provider, composite_score, created_at"


async def record_score(
    user_id: str,
    resume_id: str,
    job_title: str | None,
    jd_excerpt: str,
    provider: str,
    composite: int,
    result: dict,
) -> str:
    """Stores one ATS result and prunes the resume's older ones down to the
    last KEEP_PER_RESUME, in one transaction (rpc record_ats_score)."""
    supabase = get_supabase()

    def _q():
        return supabase.rpc(
            "record_ats_score",
            {
                "p_user_id": user_id,
                "p_resume_id": resume_id,
                "p_job_title": job_title,
                "p_jd_excerpt": jd_excerpt,
                "p_provider": provider,
                "p_composite": composite,
                "p_result": result,
                "p_keep": KEEP_PER_RESUME,
            },
        ).execute()

    return str((await run(_q)).data)


async def list_scores(
    user_id: str, resume_id: str | None, limit: int = 20, offset: int = 0
) -> list[dict]:
    supabase = get_supabase()

    def _q():
        q = supabase.table("ats_scores").select(_SUMMARY).eq("user_id", user_id)
        if resume_id:
            q = q.eq("resume_id", resume_id)
        return q.order("created_at", desc=True).range(offset, offset + limit - 1).execute()

    return (await run(_q)).data


async def get_score(user_id: str, score_id: str) -> dict | None:
    supabase = get_supabase()

    def _q():
        return (
            supabase.table("ats_scores")
            .select(_SUMMARY + ", result")
            .eq("id", score_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )

    result = await run(_q)
    return result.data if result and result.data else None


async def delete_score(user_id: str, score_id: str) -> None:
    supabase = get_supabase()

    def _q():
        return supabase.table("ats_scores").delete().eq("id", score_id).eq("user_id", user_id).execute()

    await run(_q)
