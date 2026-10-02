from app.core.db import get_supabase
from app.db.base import run


async def get_role(user_id: str) -> str | None:
    supabase = get_supabase()

    def _q():
        return supabase.table("roles").select("role").eq("user_id", user_id).maybe_single().execute()

    result = await run(_q)
    return result.data["role"] if result and result.data else None


async def has_permission(user_id: str, permission: str) -> bool:
    supabase = get_supabase()

    def _q():
        return (
            supabase.table("admin_permissions")
            .select("id")
            .eq("admin_id", user_id)
            .eq("permission_key", permission)
            .maybe_single()
            .execute()
        )

    result = await run(_q)
    return bool(result and result.data)


async def insert_question(row: dict) -> dict:
    supabase = get_supabase()

    def _q():
        return supabase.table("question_bank").insert(row).execute()

    return (await run(_q)).data[0]


async def list_questions(interview_type: str | None, limit: int = 200, offset: int = 0) -> list[dict]:
    supabase = get_supabase()

    def _q():
        q = supabase.table("question_bank").select(
            "id, type, question, test_cases, tags, created_by, created_at"
        )
        if interview_type:
            q = q.eq("type", interview_type)
        return q.order("created_at", desc=True).range(offset, offset + limit - 1).execute()

    return (await run(_q)).data


async def update_question(question_id: str, updates: dict) -> dict | None:
    supabase = get_supabase()

    def _q():
        return supabase.table("question_bank").update(updates).eq("id", question_id).execute()

    data = (await run(_q)).data
    return data[0] if data else None


async def delete_question(question_id: str) -> None:
    supabase = get_supabase()

    def _q():
        return supabase.table("question_bank").delete().eq("id", question_id).execute()

    await run(_q)


async def match_question_bank(
    interview_type: str, query_embedding: list[float], match_count: int = 2
) -> list[dict]:
    supabase = get_supabase()

    def _q():
        return supabase.rpc(
            "match_question_bank",
            {
                "query_embedding": query_embedding,
                "filter_type": interview_type,
                "match_count": match_count,
            },
        ).execute()

    return (await run(_q)).data
