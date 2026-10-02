import asyncio
from datetime import UTC, datetime

from app.core.db import get_supabase
from app.core.security import encrypt_key
from app.providers.base import ProviderRateLimitError
from app.providers.registry import get_adapter


async def submit_key(user_id: str, provider: str, slot: str, api_key: str) -> dict:
    supabase = get_supabase()
    encrypted = encrypt_key(api_key)

    def _upsert():
        return (
            supabase.table("provider_keys")
            .upsert(
                {
                    "user_id": user_id,
                    "provider": provider,
                    "slot": slot,
                    "encrypted_key": encrypted,
                    "is_valid": False,
                },
                on_conflict="user_id,provider,slot",
            )
            .execute()
        )

    result = await asyncio.to_thread(_upsert)
    row = result.data[0]

    adapter = get_adapter(provider)
    try:
        is_valid = await adapter.validate(api_key)
    except ProviderRateLimitError:
        # The key itself might be fine -- the provider is just currently
        # rate-limited -- so leave validation as "not yet confirmed" rather
        # than marking the key invalid outright.
        is_valid = False

    def _update_validity():
        return (
            supabase.table("provider_keys")
            .update(
                {
                    "is_valid": is_valid,
                    "last_validated_at": datetime.now(UTC).isoformat(),
                }
            )
            .eq("id", row["id"])
            .execute()
        )

    updated = await asyncio.to_thread(_update_validity)
    return updated.data[0]


async def list_keys(user_id: str) -> list[dict]:
    supabase = get_supabase()

    def _query():
        return (
            supabase.table("provider_keys")
            .select("id, provider, slot, is_valid, last_validated_at")
            .eq("user_id", user_id)
            .execute()
        )

    result = await asyncio.to_thread(_query)
    return result.data


async def delete_key(user_id: str, key_id: str) -> None:
    supabase = get_supabase()

    def _delete():
        return (
            supabase.table("provider_keys")
            .delete()
            .eq("id", key_id)
            .eq("user_id", user_id)
            .execute()
        )

    await asyncio.to_thread(_delete)


async def get_key_row(user_id: str, provider: str, slot: str) -> dict | None:
    """Public lookup used by the LLM gateway (llm/gateway.py), which owns
    primary -> backup failover."""
    supabase = get_supabase()

    def _query():
        return (
            supabase.table("provider_keys")
            .select("id, encrypted_key")
            .eq("user_id", user_id)
            .eq("provider", provider)
            .eq("slot", slot)
            .maybe_single()
            .execute()
        )

    result = await asyncio.to_thread(_query)
    return result.data if result else None


async def notify_user(user_id: str, message: str) -> None:
    """Public, cross-module notification helper -- see get_key_row."""
    supabase = get_supabase()

    def _insert():
        return (
            supabase.table("notifications")
            .insert({"user_id": user_id, "message": message})
            .execute()
        )

    await asyncio.to_thread(_insert)
