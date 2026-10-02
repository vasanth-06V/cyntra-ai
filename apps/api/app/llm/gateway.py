"""The single entry point for every model call.

Features say *what* they want (complete / stream / embed, with an
LLMOptions task); the gateway owns the cross-cutting behavior that used to
be re-implemented per feature:

  limiter -> adapter -> [transient retry] -> [backup-key failover] -> usage

Errors surface as HTTPException so every endpoint reports them the same way:
  412  no key configured
  429  both keys rate-limited / no backup / local rate limit
  503  provider still overloaded after retries
  422  the provider declined to answer (safety filter)
  400  the provider rejected the key itself

One hard rule, kept from the chat design: nothing is retried or failed over
once output has started streaming -- that would repeat text the user has
already seen.
"""

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from typing import TypeVar

from fastapi import HTTPException, status

from app.core.errors import AppError

from app.core.security import decrypt_key
from app.db.keys import get_key_row, insert_notification as notify_user
from app.llm import usage as usage_log
from app.llm.budget import estimate_messages_tokens, estimate_tokens
from app.llm.limiter import limiter
from app.llm.options import LLMOptions, Usage
from app.providers.base import (
    Message,
    ProviderAuthError,
    ProviderBlockedError,
    ProviderRateLimitError,
    ProviderUnavailableError,
)
from app.providers.registry import get_adapter
from app.rag.embeddings import embed_texts

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Seconds between attempts when a provider is temporarily overloaded (3
# attempts total). Provider 503s are usually momentary -- Gemini's "high
# demand" error succeeded on a plain second try in live use.
_RETRY_DELAYS = (1.0, 2.0)


async def _notify_failover(user_id: str, provider: str) -> None:
    try:
        await notify_user(
            user_id,
            f"Your primary {provider} key hit its rate limit -- switched to your backup key.",
        )
    except Exception:
        # The answer already exists; losing it over a notification would be worse.
        logger.warning("Could not record the key-failover notification", exc_info=True)


async def _primary_key(user_id: str, provider: str) -> str:
    row = await get_key_row(user_id, provider, "primary")
    if not row:
        raise AppError(
            status.HTTP_412_PRECONDITION_FAILED,
            "key_missing",
            f"No {provider} key configured",
        )
    return decrypt_key(row["encrypted_key"])


async def _backup_key(user_id: str, provider: str) -> str:
    row = await get_key_row(user_id, provider, "backup")
    if not row:
        raise AppError(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "quota_exhausted",
            f"Primary {provider} key is rate-limited and no backup key is configured",
        )
    return decrypt_key(row["encrypted_key"])


def _overloaded(provider: str) -> HTTPException:
    return AppError(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "provider_overloaded",
        f"{provider.capitalize()} is temporarily overloaded -- please try again in a moment.",
    )


def _blocked(provider: str) -> HTTPException:
    return AppError(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "reply_blocked",
        f"{provider.capitalize()} declined to answer this -- try rephrasing your message.",
    )


def _key_rejected(provider: str) -> HTTPException:
    return AppError(
        status.HTTP_400_BAD_REQUEST,
        "key_rejected",
        f"Your {provider} key was rejected -- check it in Settings -> API Keys.",
    )


async def _one_key(
    user_id: str, bucket: str, key: str, fn: Callable[[str], Awaitable[T]]
) -> T:
    """Runs fn with a single key: rate-limited, retrying transient errors."""
    attempt = 0
    while True:
        await limiter.acquire(user_id, bucket)
        try:
            return await fn(key)
        except ProviderUnavailableError:
            if attempt >= len(_RETRY_DELAYS):
                raise
            await asyncio.sleep(_RETRY_DELAYS[attempt])
            attempt += 1


async def _with_failover(
    user_id: str, provider: str, bucket: str, fn: Callable[[str], Awaitable[T]]
) -> T:
    primary = await _primary_key(user_id, provider)
    try:
        try:
            return await _one_key(user_id, bucket, primary, fn)
        except ProviderRateLimitError:
            backup = await _backup_key(user_id, provider)
            try:
                result = await _one_key(user_id, bucket, backup, fn)
            except ProviderRateLimitError as exc:
                raise AppError(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    "quota_exhausted",
                    f"Both primary and backup {provider} keys are rate-limited",
                ) from exc
            await _notify_failover(user_id, provider)
            return result
    except ProviderUnavailableError as exc:
        raise _overloaded(provider) from exc
    except ProviderAuthError as exc:
        raise _key_rejected(provider) from exc
    except ProviderBlockedError as exc:
        raise _blocked(provider) from exc


async def complete(
    user_id: str,
    provider: str,
    messages: Sequence[Message],
    options: LLMOptions | None = None,
) -> str:
    """One-shot (non-streaming) completion."""
    options = options or LLMOptions()
    adapter = get_adapter(provider)
    usage = Usage()

    async def call(api_key: str) -> str:
        parts: list[str] = []
        async for chunk in adapter.chat(
            api_key, list(messages), stream=False, options=options, usage=usage
        ):
            parts.append(chunk)
        return "".join(parts)

    text = await _with_failover(user_id, provider, provider, call)
    await usage_log.record(
        user_id,
        provider,
        "chat",
        usage,
        est_input_tokens=estimate_messages_tokens(messages),
        est_output_tokens=estimate_tokens(text),
    )
    return text


async def stream(
    user_id: str,
    provider: str,
    messages: Sequence[Message],
    options: LLMOptions | None = None,
) -> AsyncIterator[str]:
    """Streaming completion. Failures before the first chunk are retried or
    failed over; after it they propagate (see the module docstring)."""
    options = options or LLMOptions()
    adapter = get_adapter(provider)
    usage = Usage()
    sent_chars = 0

    async def one_key(api_key: str) -> AsyncIterator[str]:
        attempt = 0
        while True:
            await limiter.acquire(user_id, provider)
            sent = False
            try:
                async for chunk in adapter.chat(
                    api_key, list(messages), stream=True, options=options, usage=usage
                ):
                    sent = True
                    yield chunk
                return
            except ProviderUnavailableError:
                if sent or attempt >= len(_RETRY_DELAYS):
                    raise
                await asyncio.sleep(_RETRY_DELAYS[attempt])
                attempt += 1

    primary = await _primary_key(user_id, provider)
    chunk_sent = False

    try:
        try:
            async for chunk in one_key(primary):
                chunk_sent = True
                sent_chars += len(chunk)
                yield chunk
        except ProviderRateLimitError:
            if chunk_sent:
                raise
            backup = await _backup_key(user_id, provider)
            try:
                async for chunk in one_key(backup):
                    chunk_sent = True
                    sent_chars += len(chunk)
                    yield chunk
            except ProviderRateLimitError as exc:
                if chunk_sent:
                    raise
                raise AppError(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    "quota_exhausted",
                    f"Both primary and backup {provider} keys are rate-limited",
                ) from exc
            await _notify_failover(user_id, provider)
    except ProviderUnavailableError as exc:
        if chunk_sent:
            raise
        raise _overloaded(provider) from exc
    except ProviderAuthError as exc:
        if chunk_sent:
            raise
        raise _key_rejected(provider) from exc
    except ProviderBlockedError as exc:
        if chunk_sent:
            raise
        raise _blocked(provider) from exc

    await usage_log.record(
        user_id,
        provider,
        "chat",
        usage,
        est_input_tokens=estimate_messages_tokens(messages),
        est_output_tokens=-(-sent_chars // 4),
    )


async def embed(user_id: str, texts: list[str]) -> list[list[float]]:
    """Batched embeddings, always via the user's Gemini key (the only
    provider with an embeddings API) -- with the same backup-key failover
    as everything else, which embeddings previously lacked."""
    usage = Usage()

    async def call(api_key: str) -> list[list[float]]:
        return await embed_texts(api_key, texts, usage=usage)

    vectors = await _with_failover(user_id, "gemini", "gemini:embed", call)
    await usage_log.record(
        user_id,
        "gemini",
        "embed",
        usage,
        est_input_tokens=sum(estimate_tokens(t) for t in texts),
    )
    return vectors
