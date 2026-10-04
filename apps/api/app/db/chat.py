from app.core.db import get_supabase
from app.db.base import run


async def create_conversation(user_id: str, title: str | None) -> dict:
    supabase = get_supabase()

    def _q():
        return supabase.table("conversations").insert({"user_id": user_id, "title": title}).execute()

    return (await run(_q)).data[0]


async def list_conversations(user_id: str, limit: int = 50, offset: int = 0) -> list[dict]:
    supabase = get_supabase()

    def _q():
        return (
            supabase.table("conversations")
            .select("id, title, created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )

    return (await run(_q)).data


async def rename_conversation(user_id: str, conversation_id: str, title: str) -> dict | None:
    supabase = get_supabase()

    def _q():
        return (
            supabase.table("conversations")
            .update({"title": title})
            .eq("id", conversation_id)
            .eq("user_id", user_id)
            .execute()
        )

    rows = (await run(_q)).data
    return rows[0] if rows else None


async def get_owned_conversation(user_id: str, conversation_id: str) -> dict | None:
    supabase = get_supabase()

    def _q():
        return (
            supabase.table("conversations")
            .select("id")
            .eq("id", conversation_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )

    result = await run(_q)
    return result.data if result and result.data else None


async def list_messages(conversation_id: str, limit: int | None = None) -> list[dict]:
    """Oldest-first. With `limit`, the *latest* `limit` messages (still oldest-first)."""
    supabase = get_supabase()

    def _q():
        q = (
            supabase.table("chat_messages")
            .select("id, role, provider, content, created_at")
            .eq("conversation_id", conversation_id)
        )
        if limit is None:
            return q.order("created_at").execute()
        return q.order("created_at", desc=True).limit(limit).execute()

    data = (await run(_q)).data
    return data if limit is None else list(reversed(data))


async def append_exchange(
    conversation_id: str, user_id: str, user_text: str, assistant_text: str, provider: str
) -> None:
    """Both messages of an exchange in ONE transaction (rpc append_chat_exchange)."""
    supabase = get_supabase()

    def _q():
        return supabase.rpc(
            "append_chat_exchange",
            {
                "p_conversation_id": conversation_id,
                "p_user_id": user_id,
                "p_user_text": user_text,
                "p_assistant_text": assistant_text,
                "p_provider": provider,
            },
        ).execute()

    await run(_q)
