import asyncio
import math
from collections.abc import AsyncIterator
from functools import lru_cache

import google.generativeai as genai
from google.ai import generativelanguage as glm
from google.api_core.client_options import ClientOptions
from google.api_core.exceptions import (
    DeadlineExceeded,
    InternalServerError,
    InvalidArgument,
    NotFound,
    PermissionDenied,
    ResourceExhausted,
    ServiceUnavailable,
    Unauthenticated,
)

from app.llm.models import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL, model_for
from app.llm.options import LLMOptions, Usage
from app.providers.base import (
    Message,
    MessageRole,
    ProviderAdapter,
    ProviderAuthError,
    ProviderBlockedError,
    ProviderRateLimitError,
    ProviderUnavailableError,
)

_TRANSIENT_ERRORS = (ServiceUnavailable, InternalServerError, DeadlineExceeded)
_EMBED_BATCH_SIZE = 100  # the SDK splits larger lists itself; this is for usage counting


# Per-key clients, never the SDK's process-global default.
#
# genai.configure(api_key=...) mutates global state and the SDK builds its
# client lazily from it on the first request. With two users calling at once,
# one request could be sent with the *other* user's key -- billing the wrong
# person under BYOK. Building the client explicitly from the caller's key
# removes the shared state. (Cached per key; each is bound to the event loop
# that first used it, which is the single uvicorn loop in production.)
@lru_cache(maxsize=32)
def _generative_client(api_key: str) -> glm.GenerativeServiceAsyncClient:
    return glm.GenerativeServiceAsyncClient(client_options=ClientOptions(api_key=api_key))


@lru_cache(maxsize=32)
def _model_client(api_key: str) -> glm.ModelServiceClient:
    return glm.ModelServiceClient(client_options=ClientOptions(api_key=api_key))


def _to_gemini_contents(messages: list[Message]) -> tuple[str | None, list[dict]]:
    """Gemini has no 'system' role on messages -- system instructions are
    passed separately to the model constructor. Several system messages are
    joined rather than the last one silently winning. Returns
    (system_instruction, contents)."""
    system_parts: list[str] = []
    contents: list[dict] = []
    for m in messages:
        if m.role == MessageRole.SYSTEM:
            system_parts.append(m.content)
            continue
        role = "model" if m.role == MessageRole.ASSISTANT else "user"
        contents.append({"role": role, "parts": [m.content]})
    return ("\n\n".join(system_parts) or None), contents


def _generation_config(options: LLMOptions) -> dict:
    config: dict = {}
    if options.max_output_tokens is not None:
        config["max_output_tokens"] = options.max_output_tokens
    if options.temperature is not None:
        config["temperature"] = options.temperature
    if options.json_mode:
        config["response_mime_type"] = "application/json"
    return config


def _record_usage(usage: Usage | None, response) -> None:
    if usage is None:
        return
    usage.requests += 1
    meta = getattr(response, "usage_metadata", None)
    if meta is not None:
        usage.input_tokens += getattr(meta, "prompt_token_count", 0) or 0
        usage.output_tokens += getattr(meta, "candidates_token_count", 0) or 0


def _build_model(api_key: str, model_name: str, system_instruction: str | None):
    model = genai.GenerativeModel(model_name, system_instruction=system_instruction)
    # Public API gives no way to pass a client; the SDK only builds its
    # global default when this is None. A canary test guards that this
    # private attribute still behaves that way after an SDK upgrade.
    model._async_client = _generative_client(api_key)
    return model


class GeminiAdapter(ProviderAdapter):
    name = "gemini"

    async def validate(self, api_key: str) -> bool:
        """Lists models instead of generating text: it checks the key without
        spending any of the daily generation quota."""
        try:
            client = _model_client(api_key)
            await asyncio.to_thread(
                lambda: next(iter(genai.list_models(page_size=1, client=client)), None)
            )
            return True
        except (PermissionDenied, Unauthenticated, InvalidArgument):
            # Google reports a malformed/unknown API key as InvalidArgument
            # ("API key not valid"), not as an auth error.
            return False
        except ResourceExhausted as exc:
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
        system_instruction, contents = _to_gemini_contents(messages)
        model = _build_model(api_key, model_for(self.name, options.task), system_instruction)
        config = _generation_config(options) or None

        try:
            if stream:
                response = await model.generate_content_async(
                    contents, stream=True, generation_config=config
                )
                produced = False
                async for chunk in response:
                    try:
                        text = chunk.text
                    except ValueError:
                        continue  # a chunk with no text part (e.g. the finish marker)
                    if text:
                        produced = True
                        yield text
                _record_usage(usage, response)
                if not produced:
                    raise ProviderBlockedError("Gemini returned no text (blocked or empty)")
            else:
                response = await model.generate_content_async(
                    contents, generation_config=config
                )
                _record_usage(usage, response)
                try:
                    text = response.text
                except ValueError as exc:
                    raise ProviderBlockedError(
                        "Gemini returned no text (blocked or empty)"
                    ) from exc
                yield text
        except (PermissionDenied, Unauthenticated, InvalidArgument) as exc:
            # Google reports a revoked/malformed key as InvalidArgument.
            raise ProviderAuthError(str(exc)) from exc
        except ResourceExhausted as exc:
            raise ProviderRateLimitError(str(exc)) from exc
        except NotFound as exc:
            # e.g. a retired model name -- our configuration, not the user's.
            raise ProviderUnavailableError(f"model not found: {exc}") from exc
        except _TRANSIENT_ERRORS as exc:
            raise ProviderUnavailableError(str(exc)) from exc

    async def embed_many(
        self, api_key: str, texts: list[str], usage: Usage | None = None
    ) -> list[list[float]]:
        """One request per 100 texts (the SDK batches a list itself and
        returns {"embedding": [[...], ...]}), instead of one per text."""
        if not texts:
            return []
        try:
            result = await genai.embed_content_async(
                model=EMBEDDING_MODEL,
                content=texts,
                output_dimensionality=EMBEDDING_DIMENSIONS,
                client=_generative_client(api_key),
            )
        except (PermissionDenied, Unauthenticated, InvalidArgument) as exc:
            # Google reports a revoked/malformed key as InvalidArgument.
            raise ProviderAuthError(str(exc)) from exc
        except ResourceExhausted as exc:
            raise ProviderRateLimitError(str(exc)) from exc
        except NotFound as exc:
            # e.g. a retired model name -- our configuration, not the user's.
            raise ProviderUnavailableError(f"model not found: {exc}") from exc
        except _TRANSIENT_ERRORS as exc:
            raise ProviderUnavailableError(str(exc)) from exc

        embeddings = result["embedding"]
        if len(embeddings) != len(texts):
            raise ValueError(
                f"Embedding count mismatch: sent {len(texts)} texts, got {len(embeddings)} vectors"
            )
        if usage is not None:
            usage.requests += math.ceil(len(texts) / _EMBED_BATCH_SIZE)
        return embeddings
