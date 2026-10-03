from postgrest.exceptions import APIError

from app.core.db import get_supabase
from app.db.base import run

_LIST_COLUMNS = "id, interview_id, interview_type, overall_score, created_at, expires_at"


async def get_report(user_id: str, interview_id: str) -> dict | None:
    """The stored report (expiry is judged by the caller, with its own clock)."""
    supabase = get_supabase()

    def _q():
        return (
            supabase.table("interview_reports")
            .select(_LIST_COLUMNS + ", report_data")
            .eq("interview_id", interview_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )

    result = await run(_q)
    return result.data if result and result.data else None


async def list_reports(user_id: str, limit: int = 50, offset: int = 0) -> list[dict]:
    supabase = get_supabase()

    def _q():
        return (
            supabase.table("interview_reports")
            .select(_LIST_COLUMNS)
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )

    return (await run(_q)).data


async def save_report(
    user_id: str, interview_id: str, interview_type: str, overall_score: int, data: dict
) -> dict:
    """Stores (or replaces) the interview's report; expires_at is the database
    default of created_at + 7 days and is never touched afterwards."""
    supabase = get_supabase()

    def _delete():
        return (
            supabase.table("interview_reports")
            .delete()
            .eq("interview_id", interview_id)
            .eq("user_id", user_id)
            .execute()
        )

    def _insert():
        return (
            supabase.table("interview_reports")
            .insert(
                {
                    "user_id": user_id,
                    "interview_id": interview_id,
                    "interview_type": interview_type,
                    "overall_score": overall_score,
                    "report_data": data,
                }
            )
            .execute()
        )

    await run(_delete)  # an expired or older report is replaced, not duplicated
    try:
        return (await run(_insert)).data[0]
    except APIError as exc:
        if getattr(exc, "code", None) == "23505":  # a concurrent run won: keep its report
            existing = await get_report(user_id, interview_id)
            if existing:
                return existing
        raise


async def delete_report(user_id: str, interview_id: str) -> None:
    supabase = get_supabase()

    def _q():
        return (
            supabase.table("interview_reports")
            .delete()
            .eq("interview_id", interview_id)
            .eq("user_id", user_id)
            .execute()
        )

    await run(_q)


async def purge_expired(now_iso: str) -> int:
    """Deletes every report whose 7 days are over. Returns how many."""
    supabase = get_supabase()

    def _q():
        return supabase.table("interview_reports").delete().lt("expires_at", now_iso).execute()

    return len((await run(_q)).data or [])
