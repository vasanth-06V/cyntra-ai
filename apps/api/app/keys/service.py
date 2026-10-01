import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import TypeVar

from app.core.db import get_supabase
from app.core.security import decrypt_key, encrypt_key
from app.providers.base import ProviderRateLimitError
from app.providers.registry import get_adapter

T = TypeVar("T")


class BothKeysFailedError(Exception):
    """Raised when neither the primary nor backup key works for a provider."""


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
    """Public, cross-module lookup -- used directly by streaming consumers
    (chat/interview services) that need primary/backup key access but can't
    use call_with_failover's one-shot-call shape. See its docstring."""
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


async def call_with_failover(
    user_id: str, provider: str, fn: Callable[[str], Awaitable[T]]
) -> T:
    """Runs a one-shot async call (e.g. validate(), embed(), a non-streaming
    chat call) against the user's primary key for `provider`. On a rate-limit
    error, retries once against the backup key and notifies the user after a
    successful fallback. Raises BothKeysFailedError if neither works.

    Streaming chat failover (switching keys mid-stream) is a different
    problem -- partially-yielded output can't simply be "retried" -- and is
    handled directly in the chat/interview services that consume streaming
    responses, reusing get_key_row/notify_user from this module directly.
    """
    primary = await get_key_row(user_id, provider, "primary")
    if not primary:
        raise BothKeysFailedError(f"No {provider} key configured")

    try:
        return await fn(decrypt_key(primary["encrypted_key"]))
    except ProviderRateLimitError:
        backup = await get_key_row(user_id, provider, "backup")
        if not backup:
            raise BothKeysFailedError(
                f"Primary {provider} key is rate-limited and no backup key is configured"
            ) from None

        try:
            result = await fn(decrypt_key(backup["encrypted_key"]))
        except ProviderRateLimitError as exc:
            raise BothKeysFailedError(
                f"Both primary and backup {provider} keys are rate-limited"
            ) from exc

        await notify_user(
            user_id,
            f"Your primary {provider} key hit its rate limit -- "
            f"switched to your backup key.",
        )
        return result
