import asyncio
from collections.abc import AsyncIterator

from fastapi import HTTPException, status

from app.core.db import get_supabase
from app.keys.service import get_key_row, notify_user
from app.core.security import decrypt_key
from app.providers.base import (
    Message,
    MessageRole,
    ProviderRateLimitError,
    ProviderUnavailableError,
)
from app.providers.registry import get_adapter

# Seconds to wait between attempts when the provider is temporarily
# overloaded (3 attempts total). Providers' 503s are usually momentary --
# Gemini's "high demand" error succeeded on a plain second try in live use.
_RETRY_DELAYS = (1.0, 2.0)


async def create_conversation(user_id: str, title: str | None) -> dict:
    supabase = get_supabase()

    def _insert():
        return (
            supabase.table("conversations")
            .insert({"user_id": user_id, "title": title})
            .execute()
        )

    result = await asyncio.to_thread(_insert)
    return result.data[0]


async def list_conversations(user_id: str) -> list[dict]:
    supabase = get_supabase()

    def _query():
        return (
            supabase.table("conversations")
            .select("id, title, created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )

    result = await asyncio.to_thread(_query)
    return result.data


async def _require_owned_conversation(user_id: str, conversation_id: str) -> dict:
    supabase = get_supabase()

    def _query():
        return (
            supabase.table("conversations")
            .select("id")
            .eq("id", conversation_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )

    result = await asyncio.to_thread(_query)
    if not result or not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
        )
    return result.data


async def list_messages(user_id: str, conversation_id: str) -> list[dict]:
    await _require_owned_conversation(user_id, conversation_id)
    supabase = get_supabase()

    def _query():
        return (
            supabase.table("chat_messages")
            .select("id, role, provider, content, created_at")
            .eq("conversation_id", conversation_id)
            .order("created_at")
            .execute()
        )

    result = await asyncio.to_thread(_query)
    return result.data


async def _append_message(
    conversation_id: str, role: str, content: str, provider: str | None = None
) -> dict:
    supabase = get_supabase()

    def _insert():
        return (
            supabase.table("chat_messages")
            .insert(
                {
                    "conversation_id": conversation_id,
                    "role": role,
                    "provider": provider,
                    "content": content,
                }
            )
            .execute()
        )

    result = await asyncio.to_thread(_insert)
    return result.data[0]


async def _chat_with_retry(adapter, api_key: str, messages: list[Message]) -> AsyncIterator[str]:
    """Streams from the adapter, retrying only if it reports the provider as
    temporarily unavailable *before any output was produced* -- retrying
    after partial output would duplicate text the user already saw."""
    attempt = 0
    while True:
        chunk_sent = False
        try:
            async for chunk in adapter.chat(api_key, messages):
                chunk_sent = True
                yield chunk
            return
        except ProviderUnavailableError:
            if chunk_sent or attempt >= len(_RETRY_DELAYS):
                raise
            await asyncio.sleep(_RETRY_DELAYS[attempt])
            attempt += 1


def _row_to_message(row: dict) -> Message:
    role = MessageRole.ASSISTANT if row["role"] == "assistant" else MessageRole.USER
    return Message(role=role, content=row["content"])


async def stream_reply(
    user_id: str, conversation_id: str, provider: str, user_content: str
) -> AsyncIterator[str]:
    """Persists the user's message, builds the conversation history, streams
    the assistant's reply from `provider` (failing over to the backup key if
    the primary is rate-limited *before any output has been sent* -- once
    streaming has started, a rate-limit mid-stream can't be safely retried,
    per the documented limitation in keys/service.py), and persists the full
    assistant reply once the stream completes.
    """
    await _require_owned_conversation(user_id, conversation_id)

    history_rows = await list_messages(user_id, conversation_id)
    await _append_message(conversation_id, "user", user_content)

    messages = [_row_to_message(row) for row in history_rows]
    messages.append(Message(role=MessageRole.USER, content=user_content))

    adapter = get_adapter(provider)
    primary = await get_key_row(user_id, provider, "primary")
    if not primary:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=f"No {provider} key configured",
        )

    collected: list[str] = []
    chunk_sent = False

    try:
        try:
            primary_key = decrypt_key(primary["encrypted_key"])
            async for chunk in _chat_with_retry(adapter, primary_key, messages):
                chunk_sent = True
                collected.append(chunk)
                yield chunk
        except ProviderRateLimitError:
            if chunk_sent:
                raise

            backup = await get_key_row(user_id, provider, "backup")
            if not backup:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Primary {provider} key is rate-limited and no backup key is configured",
                ) from None

            backup_key = decrypt_key(backup["encrypted_key"])
            async for chunk in _chat_with_retry(adapter, backup_key, messages):
                chunk_sent = True
                collected.append(chunk)
                yield chunk

            await notify_user(
                user_id,
                f"Your primary {provider} key hit its rate limit -- switched to your backup key.",
            )
    except ProviderUnavailableError as exc:
        if chunk_sent:
            raise
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{provider.capitalize()} is temporarily overloaded -- please try again in a moment.",
        ) from exc

    await _append_message(conversation_id, "assistant", "".join(collected), provider)
