import time
from collections.abc import AsyncIterator

import groq
from groq import AsyncGroq

from app.llm.models import model_for, timeout_for
from app.llm.options import LLMOptions, Usage
from app.providers.base import (
    Message,
    ProviderAdapter,
    ProviderAuthError,
    ProviderBadRequestError,
    ProviderConfigError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    retry_after_from,
)

_FINISH_REASONS = {"stop": "stop", "length": "length", "content_filter": "blocked"}


# gpt-oss models reason before they answer, and the reasoning counts against
# max_tokens: without headroom a tight cap leaves an empty reply.
_REASONING_PREFIX = "openai/gpt-oss"
_REASONING_ALLOWANCE = 256


def _request_kwargs(options: LLMOptions, model: str = "") -> dict:
    kwargs: dict = {}
    reasoning = model.startswith(_REASONING_PREFIX)
    if options.max_output_tokens is not None:
        kwargs["max_tokens"] = options.max_output_tokens + (_REASONING_ALLOWANCE if reasoning else 0)
    if reasoning:
        kwargs["extra_body"] = {"reasoning_effort": "low"}  # not a typed argument in every SDK version
    if options.temperature is not None:
        kwargs["temperature"] = options.temperature
    if options.json_mode:
        # Groq requires the word "JSON" to appear in the prompt in this mode.
        kwargs["response_format"] = {"type": "json_object"}
    return kwargs


def _record_usage(usage: Usage | None, response) -> None:
    if usage is None:
        return
    usage.requests += 1
    reported = getattr(response, "usage", None)
    if reported is not None:
        usage.input_tokens += getattr(reported, "prompt_tokens", 0) or 0
        usage.output_tokens += getattr(reported, "completion_tokens", 0) or 0


def map_error(exc: Exception) -> Exception:
    """SDK exception -> typed provider error."""
    if isinstance(exc, groq.APITimeoutError):
        return ProviderTimeoutError(str(exc))
    if isinstance(exc, groq.APIConnectionError):
        return ProviderUnavailableError(str(exc))
    if isinstance(exc, groq.RateLimitError):
        return ProviderRateLimitError(str(exc), retry_after=retry_after_from(exc))
    if isinstance(exc, (groq.AuthenticationError, groq.PermissionDeniedError)):
        return ProviderAuthError(str(exc))
    if isinstance(exc, groq.NotFoundError):
        return ProviderConfigError(f"model not found: {exc}")
    if isinstance(exc, groq.BadRequestError):
        return ProviderBadRequestError(str(exc))
    if isinstance(exc, groq.APIStatusError):
        if exc.status_code >= 500:
            return ProviderUnavailableError(str(exc), retry_after_from(exc))
        return ProviderBadRequestError(str(exc))
    return exc


class GroqAdapter(ProviderAdapter):
    name = "groq"

    @staticmethod
    def _client(api_key: str, timeout: float) -> AsyncGroq:
        # No SDK-internal retries: the gateway is the only retry layer.
        return AsyncGroq(api_key=api_key, timeout=timeout, max_retries=0)

    async def validate(self, api_key: str) -> bool:
        client = self._client(api_key, timeout_for("validate"))
        try:
            # Listing models checks the key without depending on any one model
            # being available to the account (Groq has retired or restricted
            # models before) and spends no generation quota.
            await client.models.list()
            return True
        except groq.AuthenticationError:
            return False
        except groq.APIError as exc:
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
        converted = [{"role": m.role.value, "content": m.content} for m in messages]
        model = options.model_override or model_for(self.name, options.task)
        kwargs = _request_kwargs(options, model)
        if usage is not None:
            usage.model = model
        started = time.perf_counter()

        try:
            if stream:
                response = await client.chat.completions.create(
                    model=model, messages=converted, stream=True, **kwargs
                )
                first = True
                finish = None
                async for chunk in response:
                    if not chunk.choices:
                        continue
                    choice = chunk.choices[0]
                    if getattr(choice, "finish_reason", None):
                        finish = choice.finish_reason
                    delta = choice.delta.content
                    if delta:
                        if first and usage is not None:
                            usage.ttft_ms = round((time.perf_counter() - started) * 1000, 1)
                        first = False
                        yield delta
                # Streaming chunks don't carry usage; the gateway falls back
                # to an estimate, and still counts the request.
                if usage is not None:
                    usage.requests += 1
                    usage.finish_reason = _FINISH_REASONS.get(finish or "", "other") if finish else None
            else:
                response = await client.chat.completions.create(
                    model=model, messages=converted, **kwargs
                )
                _record_usage(usage, response)
                choice = response.choices[0]
                if usage is not None and getattr(choice, "finish_reason", None):
                    usage.finish_reason = _FINISH_REASONS.get(choice.finish_reason, "other")
                yield choice.message.content or ""
        except groq.APIError as exc:
            raise map_error(exc) from exc

    # No embed_many() override -- Groq has no embeddings API (see base.py).
