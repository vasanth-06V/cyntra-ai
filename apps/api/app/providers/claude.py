from collections.abc import AsyncIterator

from anthropic import AsyncAnthropic
from anthropic import (
    APIConnectionError,
    AuthenticationError,
    InternalServerError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
)

from app.llm.models import model_for
from app.llm.options import LLMOptions, Usage
from app.providers.base import (
    Message,
    MessageRole,
    ProviderAdapter,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderUnavailableError,
)

_DEFAULT_MAX_TOKENS = 4096
_TRANSIENT_ERRORS = (InternalServerError, APIConnectionError)


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
    kwargs: dict = {"max_tokens": options.max_output_tokens or _DEFAULT_MAX_TOKENS}
    if options.temperature is not None:
        kwargs["temperature"] = options.temperature
    return kwargs


def _record_usage(usage: Usage | None, message) -> None:
    if usage is None:
        return
    usage.requests += 1
    reported = getattr(message, "usage", None)
    if reported is not None:
        usage.input_tokens += getattr(reported, "input_tokens", 0) or 0
        usage.output_tokens += getattr(reported, "output_tokens", 0) or 0


class ClaudeAdapter(ProviderAdapter):
    name = "claude"

    async def validate(self, api_key: str) -> bool:
        client = AsyncAnthropic(api_key=api_key)
        try:
            await client.messages.create(
                model=model_for(self.name, "validate"),
                max_tokens=5,
                messages=[{"role": "user", "content": "hi"}],
            )
            return True
        except AuthenticationError:
            return False
        except RateLimitError as exc:
            raise ProviderRateLimitError(str(exc)) from exc
        except _TRANSIENT_ERRORS as exc:
            raise ProviderUnavailableError(str(exc)) from exc

    async def chat(
        self,
        api_key: str,
        messages: list[Message],
        stream: bool = True,
        options: LLMOptions | None = None,
        usage: Usage | None = None,
    ) -> AsyncIterator[str]:
        options = options or LLMOptions()
        client = AsyncAnthropic(api_key=api_key)
        system, converted = _to_anthropic_messages(messages)
        kwargs = _request_kwargs(options)
        if system:
            kwargs["system"] = system
        model = model_for(self.name, options.task)

        try:
            if stream:
                async with client.messages.stream(
                    model=model, messages=converted, **kwargs
                ) as response_stream:
                    async for text in response_stream.text_stream:
                        yield text
                    _record_usage(usage, await response_stream.get_final_message())
            else:
                response = await client.messages.create(
                    model=model, messages=converted, **kwargs
                )
                _record_usage(usage, response)
                yield "".join(block.text for block in response.content if block.type == "text")
        except (AuthenticationError, PermissionDeniedError) as exc:
            raise ProviderAuthError(str(exc)) from exc
        except RateLimitError as exc:
            raise ProviderRateLimitError(str(exc)) from exc
        except NotFoundError as exc:
            raise ProviderUnavailableError(f"model not found: {exc}") from exc
        except _TRANSIENT_ERRORS as exc:
            raise ProviderUnavailableError(str(exc)) from exc

    # No embed_many() override -- Claude has no embeddings API (see base.py).
