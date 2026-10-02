from app.core.db import get_supabase
from app.db.base import run


async def record_usage(params: dict) -> None:
    supabase = get_supabase()

    def _q():
        return supabase.rpc("record_llm_usage", params).execute()

    await run(_q)


async def usage_for_day(user_id: str, day: str) -> list[dict]:
    supabase = get_supabase()

    def _q():
        return (
            supabase.table("llm_usage")
            .select("provider, kind, requests, input_tokens, output_tokens")
            .eq("user_id", user_id)
            .eq("day", day)
            .execute()
        )

    return (await run(_q)).data or []
