"""The single entry point for every model call.

Features say *what* they want (complete / stream / embed, with an
LLMOptions task); the gateway owns the cross-cutting behavior:

  cooldown check -> per-key limiter -> adapter (own timeout)
      -> [retry transient errors with jittered backoff]
      -> [fail over to the backup key] -> usage + one structured log line

Errors always surface as AppError so every endpoint reports them the same way:
  412 key_missing        no key configured
  429 quota_exhausted    keys rate-limited / spent (or the local limiter said wait)
  503 provider_overloaded  provider still struggling after retries
  503 provider_misconfigured  our model name is stale (needs a deploy)
  504 provider_timeout   the provider did not answer in time
  400 key_rejected       the provider rejected the key itself
  422 reply_blocked      the provider declined to answer (safety filter)
  502 provider_bad_request / empty_reply   something on our side or an empty reply

One hard rule: nothing is retried or failed over once output has started
streaming -- that would repeat text the user has already seen.
"""

import asyncio
import dataclasses
import logging
import random
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from typing import TypeVar

from fastapi import status

from app.core.errors import AppError
from app.core.security import decrypt_key
from app.db.keys import get_key_row, insert_notification as notify_user
from app.llm import usage as usage_log
from app.llm.budget import estimate_messages_tokens, estimate_tokens, trim_to_sentence
from app.llm.completion import Completion
from app.llm.keystate import cooldowns, key_hash, seconds_until_pacific_midnight
from app.llm.limiter import limiter
from app.llm.models import FALLBACKS, timeout_for
from app.llm.options import LLMOptions, Usage
from app.providers.base import (
    Message,
    ProviderAuthError,
    ProviderBadRequestError,
    ProviderBlockedError,
    ProviderConfigError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.providers.registry import get_adapter
from app.rag.embeddings import embed_texts

logger = logging.getLogger("app.llm")

T = TypeVar("T")

# Base delays (seconds) between attempts when a provider is temporarily
# overloaded: 3 attempts in total. Each wait is jittered, and a provider's own
# Retry-After hint (capped) wins when it is longer.
_RETRY_DELAYS = (1.0, 2.0)
_MAX_HINTED_WAIT = 8.0
# A per-minute rate limit with a short hint is worth waiting out once on the
# same key before giving up on it.
_MAX_RPM_WAIT = 8.0
_DEFAULT_RPM_COOLDOWN = 60.0
# Added to twice the per-call timeout to bound a whole non-streaming call
# (limiter wait + every attempt + backoff).
_DEADLINE_SLACK = 10.0


# --------------------------------------------------------------------------
# keys


async def _primary_key(user_id: str, provider: str) -> str:
    row = await get_key_row(user_id, provider, "primary")
    if not row:
        raise AppError(
            status.HTTP_412_PRECONDITION_FAILED, "key_missing", f"No {provider} key configured"
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


async def _notify_failover(user_id: str, provider: str) -> None:
    try:
        await notify_user(
            user_id,
            f"Your primary {provider} key hit its rate limit -- switched to your backup key.",
        )
    except Exception:
        # The answer already exists; losing it over a notification would be worse.
        logger.warning("Could not record the key-failover notification", exc_info=True)


def _note_exhausted(provider: str, khash: str, exc: ProviderRateLimitError) -> None:
    """Remember a spent key so the next calls skip it instead of re-probing."""
    if exc.kind == "cooldown":
        return
    if exc.kind == "rpd":
        seconds = seconds_until_pacific_midnight()
    else:
        seconds = exc.retry_after or _DEFAULT_RPM_COOLDOWN
    cooldowns.set(provider, khash, seconds)


# --------------------------------------------------------------------------
# error translation


def _overloaded(provider: str) -> AppError:
    return AppError(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "provider_overloaded",
        f"{provider.capitalize()} is temporarily overloaded -- please try again in a moment.",
    )


def _blocked(provider: str) -> AppError:
    return AppError(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "reply_blocked",
        f"{provider.capitalize()} declined to answer this -- try rephrasing your message.",
    )


def _key_rejected(provider: str) -> AppError:
    return AppError(
        status.HTTP_400_BAD_REQUEST,
        "key_rejected",
        f"Your {provider} key was rejected -- check it in Settings -> API Keys.",
    )


def _both_exhausted(provider: str, exc: ProviderRateLimitError) -> AppError:
    hint = ""
    if exc.retry_after and exc.retry_after >= 60:
        hint = f" Try again in about {round(exc.retry_after / 60)} min."
    return AppError(
        status.HTTP_429_TOO_MANY_REQUESTS,
        "quota_exhausted",
        f"Both primary and backup {provider} keys are rate-limited.{hint}",
    )


def _translate(exc: ProviderError, provider: str) -> AppError:
    """Provider-level failure -> the one user-facing outcome."""
    if isinstance(exc, ProviderUnavailableError):
        return _overloaded(provider)
    if isinstance(exc, ProviderTimeoutError):
        return AppError(
            status.HTTP_504_GATEWAY_TIMEOUT,
            "provider_timeout",
            f"{provider.capitalize()} took too long to answer -- please try again.",
        )
    if isinstance(exc, ProviderAuthError):
        return _key_rejected(provider)
    if isinstance(exc, ProviderBlockedError):
        return _blocked(provider)
    if isinstance(exc, ProviderConfigError):
        logger.error("Provider model configuration is stale: %s", exc)
        return AppError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "provider_misconfigured",
            f"{provider.capitalize()}'s model is unavailable right now. This needs a fix on our side.",
        )
    if isinstance(exc, ProviderBadRequestError):
        logger.error("Provider rejected our request: %s", exc)
        return AppError(
            status.HTTP_502_BAD_GATEWAY,
            "provider_bad_request",
            f"{provider.capitalize()} couldn't process that request. If it keeps happening, let us know.",
        )
    if isinstance(exc, ProviderRateLimitError):
        return _both_exhausted(provider, exc)
    return AppError(status.HTTP_502_BAD_GATEWAY, "provider_error", "The AI provider returned an error.")


# --------------------------------------------------------------------------
# tracing


@dataclasses.dataclass
class _Trace:
    feature: str | None
    task: str
    provider: str
    slot: str = "primary"
    attempts: int = 0
    retries: int = 0
    failed_over: bool = False
    outcome: str = "ok"


def _new_trace(provider: str, options: LLMOptions) -> _Trace:
    return _Trace(feature=options.feature, task=options.task, provider=provider)


def _log_call(trace: _Trace, usage: Usage, options: LLMOptions, started: float, kind: str) -> None:
    logger.info(
        "llm_call",
        extra={
            "kind": kind,
            "feature": trace.feature,
            "task": trace.task,
            "provider": trace.provider,
            "llm_model": usage.model,
            "key_slot": trace.slot,
            "prompt_id": options.prompt_id,
            "prompt_version": options.prompt_version,
            "attempts": trace.attempts,
            "retries": trace.retries,
            "failed_over": trace.failed_over,
            "outcome": trace.outcome,
            "finish_reason": usage.finish_reason,
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            "ttft_ms": usage.ttft_ms,
            "in_tokens": usage.input_tokens,
            "out_tokens": usage.output_tokens,
            "thought_tokens": usage.thought_tokens,
        },
    )


# --------------------------------------------------------------------------
# one key, with retries


def _backoff(attempt: int, retry_after: float | None) -> float:
    base = _RETRY_DELAYS[attempt]
    if retry_after:
        base = max(base, min(retry_after, _MAX_HINTED_WAIT))
    # "Equal jitter": never zero (unless the base is), never the same twice.
    return base / 2 + random.uniform(0, base / 2)


async def _one_key(
    provider: str,
    bucket: str,
    key: str,
    fn: Callable[[str], Awaitable[T]],
    options: LLMOptions,
    trace: _Trace,
) -> T:
    """Runs fn with a single key: cooldown-checked, rate-limited, retrying
    transient failures."""
    khash = key_hash(key)
    left = cooldowns.remaining(provider, khash)
    if left > 0:
        raise ProviderRateLimitError("key is cooling down", kind="cooldown", retry_after=left)

    attempt = 0
    timeout_retried = False
    rpm_waited = False
    while True:
        await limiter.acquire(khash, bucket, options.priority)
        trace.attempts += 1
        try:
            result = await fn(key)
            if rpm_waited:
                cooldowns.forget(provider, khash)
            return result
        except ProviderUnavailableError as exc:
            if attempt >= len(_RETRY_DELAYS):
                raise
            await asyncio.sleep(_backoff(attempt, exc.retry_after))
            attempt += 1
            trace.retries += 1
        except ProviderTimeoutError:
            if timeout_retried or attempt >= len(_RETRY_DELAYS):
                raise
            timeout_retried = True
            attempt += 1
            trace.retries += 1
        except ProviderRateLimitError as exc:
            _note_exhausted(provider, khash, exc)
            if exc.kind == "rpm" and not rpm_waited and (exc.retry_after or _MAX_RPM_WAIT) <= _MAX_RPM_WAIT:
                rpm_waited = True
                trace.retries += 1
                await asyncio.sleep(exc.retry_after or 1.0)
                continue
            raise


async def _with_failover(
    user_id: str,
    provider: str,
    bucket: str,
    fn: Callable[[str], Awaitable[T]],
    options: LLMOptions,
    trace: _Trace,
) -> T:
    primary = await _primary_key(user_id, provider)
    try:
        try:
            return await _one_key(provider, bucket, primary, fn, options, trace)
        except ProviderRateLimitError:
            backup = await _backup_key(user_id, provider)
            trace.slot, trace.failed_over = "backup", True
            try:
                result = await _one_key(provider, bucket, backup, fn, options, trace)
            except ProviderRateLimitError as exc:
                raise _both_exhausted(provider, exc) from exc
            await _notify_failover(user_id, provider)
            return result
    except ProviderError as exc:
        trace.outcome = type(exc).__name__
        raise _translate(exc, provider) from exc


# --------------------------------------------------------------------------
# public API


async def complete_full(
    user_id: str,
    provider: str,
    messages: Sequence[Message],
    options: LLMOptions | None = None,
) -> Completion:
    """One-shot (non-streaming) completion, with how it ended."""
    options = options or LLMOptions()
    adapter = get_adapter(provider)
    usage = Usage()
    trace = _new_trace(provider, options)
    started = time.perf_counter()
    # The whole call -- limiter wait, every attempt, backoff -- is bounded.
    deadline = (options.timeout_s or timeout_for(options.task)) * 2 + _DEADLINE_SLACK

    current = options

    async def call(api_key: str) -> str:
        parts: list[str] = []
        async for chunk in adapter.chat(
            api_key, list(messages), stream=False, options=current, usage=usage
        ):
            parts.append(chunk)
        return "".join(parts)

    text = ""
    try:
        async with asyncio.timeout(deadline):
            fallbacks = [None, *FALLBACKS.get(provider, {}).get(options.task, [])]
            for model in fallbacks:
                current = dataclasses.replace(options, model_override=model) if model else options
                try:
                    text = await _with_failover(user_id, provider, provider, call, current, trace)
                    break
                except AppError as err:
                    # A stale model name: try the next pinned fallback, if any.
                    if err.code != "provider_misconfigured" or model == fallbacks[-1]:
                        raise

            # A reply that is empty because "thinking" ate the whole token
            # budget gets one more try with room to answer.
            if not text.strip() and usage.finish_reason == "length" and current.max_output_tokens:
                current = dataclasses.replace(current, max_output_tokens=current.max_output_tokens * 2)
                trace.retries += 1
                text = await _with_failover(user_id, provider, provider, call, current, trace)
    except TimeoutError as exc:
        trace.outcome = "deadline"
        _log_call(trace, usage, options, started, "complete")
        raise AppError(
            status.HTTP_504_GATEWAY_TIMEOUT,
            "provider_timeout",
            f"{provider.capitalize()} took too long to answer -- please try again.",
        ) from exc
    except AppError:
        if trace.outcome == "ok":
            trace.outcome = "error"
        _log_call(trace, usage, options, started, "complete")
        raise

    if not text.strip():
        trace.outcome = "empty"
        _log_call(trace, usage, options, started, "complete")
        raise AppError(
            status.HTTP_502_BAD_GATEWAY,
            "empty_reply",
            "The model returned an empty reply -- please try again.",
        )
    if usage.finish_reason == "length" and options.trim_on_length:
        text = trim_to_sentence(text)

    _log_call(trace, usage, options, started, "complete")
    await usage_log.record(
        user_id,
        provider,
        "chat",
        usage,
        est_input_tokens=estimate_messages_tokens(messages),
        est_output_tokens=estimate_tokens(text),
    )
    return Completion(
        text=text,
        finish_reason=usage.finish_reason,
        usage=usage,
        provider=provider,
        model=usage.model,
        latency_ms=round((time.perf_counter() - started) * 1000, 1),
        attempts=trace.attempts,
        failed_over=trace.failed_over,
    )


async def complete(
    user_id: str,
    provider: str,
    messages: Sequence[Message],
    options: LLMOptions | None = None,
) -> str:
    """One-shot (non-streaming) completion; the reply text."""
    return (await complete_full(user_id, provider, messages, options)).text


async def stream(
    user_id: str,
    provider: str,
    messages: Sequence[Message],
    options: LLMOptions | None = None,
) -> AsyncIterator[str]:
    """Streaming completion. Failures before the first chunk are retried or
    failed over; after it they propagate (see the module docstring). Usage is
    recorded even if the consumer disconnects or the stream breaks midway --
    the provider still counted that request."""
    options = options or LLMOptions()
    adapter = get_adapter(provider)
    usage = Usage()
    trace = _new_trace(provider, options)
    started = time.perf_counter()
    sent_chars = 0
    chunk_sent = False

    async def one_key(slot: str, api_key: str) -> AsyncIterator[str]:
        nonlocal sent_chars, chunk_sent
        khash = key_hash(api_key)
        left = cooldowns.remaining(provider, khash)
        if left > 0:
            raise ProviderRateLimitError("key is cooling down", kind="cooldown", retry_after=left)

        attempt = 0
        timeout_retried = False
        while True:
            await limiter.acquire(khash, provider, options.priority)
            trace.attempts += 1
            sent_here = False
            try:
                async for chunk in adapter.chat(
                    api_key, list(messages), stream=True, options=options, usage=usage
                ):
                    sent_here = chunk_sent = True
                    sent_chars += len(chunk)
                    yield chunk
                return
            except ProviderUnavailableError as exc:
                if sent_here or attempt >= len(_RETRY_DELAYS):
                    raise
                await asyncio.sleep(_backoff(attempt, exc.retry_after))
                attempt += 1
                trace.retries += 1
            except ProviderTimeoutError:
                if sent_here or timeout_retried or attempt >= len(_RETRY_DELAYS):
                    raise
                timeout_retried = True
                attempt += 1
                trace.retries += 1
            except ProviderRateLimitError as exc:
                _note_exhausted(provider, khash, exc)
                raise

    try:
        primary = await _primary_key(user_id, provider)
        try:
            try:
                async for chunk in one_key("primary", primary):
                    yield chunk
            except ProviderRateLimitError:
                if chunk_sent:
                    raise
                backup = await _backup_key(user_id, provider)
                trace.slot, trace.failed_over = "backup", True
                try:
                    async for chunk in one_key("backup", backup):
                        yield chunk
                except ProviderRateLimitError as exc:
                    if chunk_sent:
                        raise
                    raise _both_exhausted(provider, exc) from exc
                await _notify_failover(user_id, provider)
        except ProviderError as exc:
            trace.outcome = type(exc).__name__
            if chunk_sent:
                raise
            raise _translate(exc, provider) from exc
    except BaseException as exc:
        if trace.outcome == "ok":
            trace.outcome = "cancelled" if isinstance(exc, (asyncio.CancelledError, GeneratorExit)) else "error"
        raise
    finally:
        _log_call(trace, usage, options, started, "stream")
        if chunk_sent or usage.requests:
            # Counted on every exit path -- completion, error, or disconnect.
            await usage_log.record(
                user_id,
                provider,
                "chat",
                usage,
                est_input_tokens=estimate_messages_tokens(messages),
                est_output_tokens=-(-sent_chars // 4),
            )


async def embed(user_id: str, texts: list[str], kind: str = "doc") -> list[list[float]]:
    """Batched embeddings, always via the user's Gemini key (the only
    provider with an embeddings API) -- with the same cooldown/limiter/backup
    handling as everything else. kind="doc" for text that will be searched,
    "query" for text used to search with."""
    options = LLMOptions(task="embed", feature="embed")
    usage = Usage()
    trace = _new_trace("gemini", options)
    started = time.perf_counter()

    async def call(api_key: str) -> list[list[float]]:
        return await embed_texts(api_key, texts, usage=usage, kind=kind)

    try:
        async with asyncio.timeout(70):
            vectors = await _with_failover(user_id, "gemini", "gemini:embed", call, options, trace)
    except TimeoutError as exc:
        trace.outcome = "deadline"
        _log_call(trace, usage, options, started, "embed")
        raise AppError(
            status.HTTP_504_GATEWAY_TIMEOUT,
            "provider_timeout",
            "Gemini took too long to answer -- please try again.",
        ) from exc
    except AppError:
        trace.outcome = trace.outcome if trace.outcome != "ok" else "error"
        _log_call(trace, usage, options, started, "embed")
        raise

    _log_call(trace, usage, options, started, "embed")
    await usage_log.record(
        user_id,
        "gemini",
        "embed",
        usage,
        est_input_tokens=sum(estimate_tokens(t) for t in texts),
    )
    return vectors
