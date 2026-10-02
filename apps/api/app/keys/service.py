import asyncio
from datetime import UTC, datetime

from fastapi import HTTPException, status

from app.core.db import get_supabase
from app.core.security import encrypt_key
from app.providers.base import ProviderRateLimitError, ProviderUnavailableError
from app.providers.registry import get_adapter


async def submit_key(user_id: str, provider: str, slot: str, api_key: str) -> dict:
    """Validates first and only stores a key that passed, so re-saving can
    never replace a working key with a bad or unconfirmed one (which would
    bounce the user back to onboarding)."""
    adapter = get_adapter(provider)
    try:
        is_valid = await adapter.validate(api_key)
    except ProviderRateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"{provider.capitalize()} is rate-limiting right now, so the key couldn't be checked. Nothing was saved -- try again in a minute.",
        ) from exc
    except ProviderUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{provider.capitalize()} is temporarily unavailable, so the key couldn't be checked. Nothing was saved -- try again shortly.",
        ) from exc

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{provider.capitalize()} rejected this key -- double-check it's correct. Nothing was saved.",
        )

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
                    "is_valid": True,
                    "last_validated_at": datetime.now(UTC).isoformat(),
                },
                on_conflict="user_id,provider,slot",
            )
            .execute()
        )

    result = await asyncio.to_thread(_upsert)
    return result.data[0]


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
