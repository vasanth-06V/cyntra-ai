import asyncio
from collections.abc import AsyncIterator

from fastapi import HTTPException, status

from app.core.db import get_supabase
from app.llm import gateway
from app.llm.options import LLMOptions
from app.providers.base import Message, MessageRole

_OPTIONS = LLMOptions(task="chat")


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


def _row_to_message(row: dict) -> Message:
    role = MessageRole.ASSISTANT if row["role"] == "assistant" else MessageRole.USER
    return Message(role=role, content=row["content"])


async def stream_reply(
    user_id: str, conversation_id: str, provider: str, user_content: str
) -> AsyncIterator[str]:
    """Persists the user's message, builds the conversation history, streams
    the assistant's reply through the LLM gateway (which owns key failover,
    transient-error retry, rate limiting and usage -- see llm/gateway.py), and
    persists the full reply once the stream completes."""
    await _require_owned_conversation(user_id, conversation_id)

    history_rows = await list_messages(user_id, conversation_id)
    await _append_message(conversation_id, "user", user_content)

    messages = [_row_to_message(row) for row in history_rows]
    messages.append(Message(role=MessageRole.USER, content=user_content))

    collected: list[str] = []
    async for chunk in gateway.stream(user_id, provider, messages, _OPTIONS):
        collected.append(chunk)
        yield chunk

    await _append_message(conversation_id, "assistant", "".join(collected), provider)
