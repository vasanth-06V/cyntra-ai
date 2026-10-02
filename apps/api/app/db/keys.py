from app.core.db import get_supabase
from app.db.base import run


async def upsert_key(user_id: str, provider: str, slot: str, encrypted: str, validated_at: str) -> dict:
    supabase = get_supabase()

    def _q():
        return (
            supabase.table("provider_keys")
            .upsert(
                {
                    "user_id": user_id,
                    "provider": provider,
                    "slot": slot,
                    "encrypted_key": encrypted,
                    "is_valid": True,
                    "last_validated_at": validated_at,
                },
                on_conflict="user_id,provider,slot",
            )
            .execute()
        )

    return (await run(_q)).data[0]


async def list_keys(user_id: str) -> list[dict]:
    supabase = get_supabase()

    def _q():
        return (
            supabase.table("provider_keys")
            .select("id, provider, slot, is_valid, last_validated_at")
            .eq("user_id", user_id)
            .execute()
        )

    return (await run(_q)).data


async def delete_key(user_id: str, key_id: str) -> None:
    supabase = get_supabase()

    def _q():
        return (
            supabase.table("provider_keys").delete().eq("id", key_id).eq("user_id", user_id).execute()
        )

    await run(_q)


async def get_key_row(user_id: str, provider: str, slot: str) -> dict | None:
    supabase = get_supabase()

    def _q():
        return (
            supabase.table("provider_keys")
            .select("id, encrypted_key")
            .eq("user_id", user_id)
            .eq("provider", provider)
            .eq("slot", slot)
            .maybe_single()
            .execute()
        )

    result = await run(_q)
    return result.data if result else None


async def insert_notification(user_id: str, message: str) -> None:
    supabase = get_supabase()

    def _q():
        return supabase.table("notifications").insert({"user_id": user_id, "message": message}).execute()

    await run(_q)
