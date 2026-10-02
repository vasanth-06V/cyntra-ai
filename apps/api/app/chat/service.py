from collections.abc import AsyncIterator

from fastapi import status

from app.core.errors import AppError
from app.db import chat as chat_repo
from app.llm import gateway
from app.llm.budget import ensure_user_first, fit_to_budget
from app.llm.options import LLMOptions
from app.providers.base import Message, MessageRole

_OPTIONS = LLMOptions(task="chat")

# Only the recent window is sent: input stays bounded however long the chat gets.
_MAX_HISTORY_MESSAGES = 10
_HISTORY_TOKEN_BUDGET = 2000

# What the UI loads when it opens a conversation (newest N, shown oldest-first).
DEFAULT_MESSAGE_PAGE = 200


async def create_conversation(user_id: str, title: str | None) -> dict:
    return await chat_repo.create_conversation(user_id, title)


async def list_conversations(user_id: str, limit: int = 50, offset: int = 0) -> list[dict]:
    return await chat_repo.list_conversations(user_id, limit, offset)


async def _require_owned_conversation(user_id: str, conversation_id: str) -> dict:
    row = await chat_repo.get_owned_conversation(user_id, conversation_id)
    if not row:
        raise AppError(status.HTTP_404_NOT_FOUND, "not_found", "Conversation not found")
    return row


async def list_messages(user_id: str, conversation_id: str, limit: int = DEFAULT_MESSAGE_PAGE) -> list[dict]:
    await _require_owned_conversation(user_id, conversation_id)
    return await chat_repo.list_messages(conversation_id, limit)


async def _append_message(
    conversation_id: str, role: str, content: str, provider: str | None = None
) -> dict:
    return await chat_repo.append_message(conversation_id, role, content, provider)


def _row_to_message(row: dict) -> Message:
    role = MessageRole.ASSISTANT if row["role"] == "assistant" else MessageRole.USER
    return Message(role=role, content=row["content"])


async def stream_reply(
    user_id: str, conversation_id: str, provider: str, user_content: str
) -> AsyncIterator[str]:
    """Builds the conversation history, streams the assistant's reply through
    the LLM gateway (which owns key failover, transient-error retry, rate
    limiting and usage -- see llm/gateway.py), and persists both messages once
    the reply has completed."""
    await _require_owned_conversation(user_id, conversation_id)

    # Only the window the model will see is fetched, not the whole history.
    history_rows = await chat_repo.list_messages(conversation_id, _MAX_HISTORY_MESSAGES)

    messages = [_row_to_message(row) for row in history_rows]
    messages.append(Message(role=MessageRole.USER, content=user_content))
    messages = ensure_user_first(fit_to_budget(messages, _HISTORY_TOKEN_BUDGET, keep_leading=0))

    collected: list[str] = []
    async for chunk in gateway.stream(user_id, provider, messages, _OPTIONS):
        collected.append(chunk)
        yield chunk

    # Both messages are saved only once the reply completed: a failed send
    # leaves no orphaned user message, so the user's retry doesn't duplicate it
    # or produce back-to-back user turns in the history.
    await _append_message(conversation_id, "user", user_content)
    await _append_message(conversation_id, "assistant", "".join(collected), provider)
