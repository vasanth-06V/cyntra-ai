from app.core.db import get_supabase
from app.db.base import run


async def record_usage(params: dict) -> None:
    supabase = get_supabase()

    def _q():
        return supabase.rpc("record_llm_usage", params).execute()

    await run(_q)


async def usage_for_days(user_id: str, days: list[str]) -> list[dict]:
    supabase = get_supabase()

    def _q():
        return (
            supabase.table("llm_usage")
            .select("provider, kind, day, requests, input_tokens, output_tokens, thought_tokens")
            .eq("user_id", user_id)
            .in_("day", days)
            .execute()
        )

    return (await run(_q)).data or []
