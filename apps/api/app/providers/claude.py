import time
from collections.abc import AsyncIterator

import anthropic
from anthropic import AsyncAnthropic

from app.llm.models import model_for, timeout_for
from app.llm.options import LLMOptions, Usage
from app.providers.base import (
    Message,
    MessageRole,
    ProviderAdapter,
    ProviderAuthError,
    ProviderBadRequestError,
    ProviderBlockedError,
    ProviderConfigError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    retry_after_from,
)

_DEFAULT_MAX_TOKENS = 4096
# Newer Claude models reason adaptively and that reasoning shares max_tokens
# (the pinned SDK predates the controls to turn it down), so never run a short
# task with a tiny cap or the reply could come back empty.
_MIN_MAX_TOKENS = 1024

_STOP_REASONS = {
    "end_turn": "stop",
    "stop_sequence": "stop",
    "max_tokens": "length",
    "refusal": "refusal",
}


def _to_anthropic_messages(messages: list[Message]) -> tuple[str | None, list[dict]]:
    """Several system messages are joined rather than the last silently
    winning."""
    system_parts: list[str] = []
    converted: list[dict] = []
    for m in messages:
        if m.role == MessageRole.SYSTEM:
            system_parts.append(m.content)
            continue
        converted.append({"role": m.role.value, "content": m.content})
    return ("\n\n".join(system_parts) or None), converted


def _request_kwargs(options: LLMOptions) -> dict:
    cap = options.max_output_tokens or _DEFAULT_MAX_TOKENS
    kwargs: dict = {"max_tokens": max(cap, _MIN_MAX_TOKENS)}
    if options.temperature is not None:
        kwargs["temperature"] = options.temperature
    return kwargs


def _record_usage(usage: Usage | None, message, started: float | None = None) -> None:
    if usage is None:
        return
    usage.requests += 1
    reported = getattr(message, "usage", None)
    if reported is not None:
        usage.input_tokens += getattr(reported, "input_tokens", 0) or 0
        usage.output_tokens += getattr(reported, "output_tokens", 0) or 0
        usage.cached_tokens += getattr(reported, "cache_read_input_tokens", 0) or 0
    usage.finish_reason = _STOP_REASONS.get(getattr(message, "stop_reason", None) or "", "other") if getattr(message, "stop_reason", None) else usage.finish_reason


def map_error(exc: Exception) -> Exception:
    """SDK exception -> typed provider error (anything unknown becomes a
    generic unavailable/bad-request, never a raw SDK error)."""
    if isinstance(exc, anthropic.APITimeoutError):
        return ProviderTimeoutError(str(exc))
    if isinstance(exc, anthropic.APIConnectionError):
        return ProviderUnavailableError(str(exc))
    if isinstance(exc, anthropic.RateLimitError):
        return ProviderRateLimitError(str(exc), retry_after=retry_after_from(exc))
    if isinstance(exc, (anthropic.AuthenticationError, anthropic.PermissionDeniedError)):
        return ProviderAuthError(str(exc))
    if isinstance(exc, anthropic.NotFoundError):
        return ProviderConfigError(f"model not found: {exc}")
    if isinstance(exc, anthropic.BadRequestError):
        return ProviderBadRequestError(str(exc))
    if isinstance(exc, anthropic.APIStatusError):
        # 5xx, and 529 "overloaded"
        if exc.status_code >= 500:
            return ProviderUnavailableError(str(exc), retry_after_from(exc))
        return ProviderBadRequestError(str(exc))
    return exc


class ClaudeAdapter(ProviderAdapter):
    name = "claude"

    @staticmethod
    def _client(api_key: str, timeout: float) -> AsyncAnthropic:
        # No SDK-internal retries: the gateway is the only retry layer, so
        # attempts are counted, spaced and failed-over in one place.
        return AsyncAnthropic(api_key=api_key, timeout=timeout, max_retries=0)

    async def validate(self, api_key: str) -> bool:
        client = self._client(api_key, timeout_for("validate"))
        try:
            await client.messages.create(
                model=model_for(self.name, "validate"),
                max_tokens=16,
                messages=[{"role": "user", "content": "hi"}],
            )
            return True
        except anthropic.AuthenticationError:
            return False
        except anthropic.APIError as exc:
            raise map_error(exc) from exc

    async def chat(
        self,
        api_key: str,
        messages: list[Message],
        stream: bool = True,
        options: LLMOptions | None = None,
        usage: Usage | None = None,
    ) -> AsyncIterator[str]:
        options = options or LLMOptions()
        timeout = options.timeout_s or timeout_for(options.task)
        client = self._client(api_key, timeout)
        system, converted = _to_anthropic_messages(messages)
        kwargs = _request_kwargs(options)
        if system:
            kwargs["system"] = system
        model = options.model_override or model_for(self.name, options.task)
        if usage is not None:
            usage.model = model
        started = time.perf_counter()

        try:
            if stream:
                first = True
                async with client.messages.stream(
                    model=model, messages=converted, **kwargs
                ) as response_stream:
                    async for text in response_stream.text_stream:
                        if first and usage is not None:
                            usage.ttft_ms = round((time.perf_counter() - started) * 1000, 1)
                        first = False
                        yield text
                    final = await response_stream.get_final_message()
                    _record_usage(usage, final)
                    if final.stop_reason == "refusal" and first:
                        raise ProviderBlockedError("Claude declined to answer")
            else:
                response = await client.messages.create(
                    model=model, messages=converted, **kwargs
                )
                _record_usage(usage, response)
                text = "".join(block.text for block in response.content if block.type == "text")
                if response.stop_reason == "refusal" and not text:
                    raise ProviderBlockedError("Claude declined to answer")
                yield text
        except anthropic.APIError as exc:
            raise map_error(exc) from exc

    # No embed_many() override -- Claude has no embeddings API (see base.py).
