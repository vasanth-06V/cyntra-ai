import logging
from collections.abc import AsyncIterator

from fastapi import status

from app.core.errors import AppError
from app.db import chat as chat_repo
from app.llm import gateway
from app.llm.budget import ensure_user_first, fit_to_budget
from app.llm.options import LLMOptions
from app.providers.base import Message, MessageRole

logger = logging.getLogger(__name__)

_OPTIONS = LLMOptions(task="chat", feature="chat")

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


_append_exchange = chat_repo.append_exchange

# One reply at a time per conversation (per process). A double-click or a retry
# while the first reply is still streaming gets a clear 409 instead of a second
# paid LLM call and two interleaved answers.
_replies_in_flight: set[str] = set()


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
    if conversation_id in _replies_in_flight:
        raise AppError(
            status.HTTP_409_CONFLICT,
            "reply_in_progress",
            "The previous reply is still being written -- one moment.",
        )
    _replies_in_flight.add(conversation_id)
    try:
        await _require_owned_conversation(user_id, conversation_id)

        # Only the window the model will see is fetched, not the whole history.
        history_rows = await chat_repo.list_messages(conversation_id, _MAX_HISTORY_MESSAGES)

        messages = [_row_to_message(row) for row in history_rows]
        messages.append(Message(role=MessageRole.USER, content=user_content))
        messages = ensure_user_first(fit_to_budget(messages, _HISTORY_TOKEN_BUDGET, keep_leading=0))

        collected: list[str] = []
        try:
            async for chunk in gateway.stream(user_id, provider, messages, _OPTIONS):
                collected.append(chunk)
                yield chunk
        finally:
            # Saved on every exit once the user has seen any text -- completion, a
            # mid-stream provider error, or the client disconnecting -- so what
            # they read is what is in the history. A send that failed before the
            # first word saves nothing, so a retry can't duplicate the message.
            if collected:
                try:
                    await _append_exchange(
                        conversation_id, user_id, user_content, "".join(collected), provider
                    )
                except Exception:
                    logger.warning("Could not save the chat exchange", exc_info=True)
    finally:
        _replies_in_flight.discard(conversation_id)
