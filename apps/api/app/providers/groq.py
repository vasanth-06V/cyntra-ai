from collections.abc import AsyncIterator

from groq import AsyncGroq
from groq import (
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
    ProviderAdapter,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderUnavailableError,
)

_TRANSIENT_ERRORS = (InternalServerError, APIConnectionError)


def _request_kwargs(options: LLMOptions) -> dict:
    kwargs: dict = {}
    if options.max_output_tokens is not None:
        kwargs["max_tokens"] = options.max_output_tokens
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


class GroqAdapter(ProviderAdapter):
    name = "groq"

    async def validate(self, api_key: str) -> bool:
        client = AsyncGroq(api_key=api_key)
        try:
            await client.chat.completions.create(
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
        client = AsyncGroq(api_key=api_key)
        converted = [{"role": m.role.value, "content": m.content} for m in messages]
        kwargs = _request_kwargs(options)
        model = model_for(self.name, options.task)

        try:
            if stream:
                response = await client.chat.completions.create(
                    model=model, messages=converted, stream=True, **kwargs
                )
                async for chunk in response:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        yield delta
                # Streaming chunks don't carry usage; the gateway falls back
                # to an estimate, and still counts the request.
                if usage is not None:
                    usage.requests += 1
            else:
                response = await client.chat.completions.create(
                    model=model, messages=converted, **kwargs
                )
                _record_usage(usage, response)
                yield response.choices[0].message.content or ""
        except (AuthenticationError, PermissionDeniedError) as exc:
            raise ProviderAuthError(str(exc)) from exc
        except RateLimitError as exc:
            raise ProviderRateLimitError(str(exc)) from exc
        except NotFoundError as exc:
            raise ProviderUnavailableError(f"model not found: {exc}") from exc
        except _TRANSIENT_ERRORS as exc:
            raise ProviderUnavailableError(str(exc)) from exc

    # No embed_many() override -- Groq has no embeddings API (see base.py).
