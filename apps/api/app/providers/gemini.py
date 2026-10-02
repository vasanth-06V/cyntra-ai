import asyncio
from collections.abc import AsyncIterator

import google.generativeai as genai
from google.api_core.exceptions import (
    InvalidArgument,
    PermissionDenied,
    ResourceExhausted,
    Unauthenticated,
)

from app.providers.base import Message, MessageRole, ProviderAdapter, ProviderAuthError, ProviderRateLimitError

# "-latest" aliases track Google's current model rather than a pinned
# version: the pinned gemini-1.5-flash this originally used was retired and
# broke key validation outright (a 404 surfaced as a 500 on first live use).
_MODEL_NAME = "gemini-flash-latest"

# text-embedding-004 is gone; gemini-embedding-001 is the current model.
# It returns 3072 dims by default, so it's requested at 768 to match the
# vector(768) columns in the schema (cosine distance is scale-invariant, so
# the truncated vectors are fine for similarity search).
_EMBEDDING_MODEL = "models/gemini-embedding-001"
EMBEDDING_DIMENSIONS = 768


def _to_gemini_contents(messages: list[Message]) -> tuple[str | None, list[dict]]:
    """Gemini has no 'system' role on messages -- system instructions are
    passed separately to the model constructor. Returns
    (system_instruction, contents)."""
    system_instruction = None
    contents: list[dict] = []
    for m in messages:
        if m.role == MessageRole.SYSTEM:
            system_instruction = m.content
            continue
        role = "model" if m.role == MessageRole.ASSISTANT else "user"
        contents.append({"role": role, "parts": [m.content]})
    return system_instruction, contents


class GeminiAdapter(ProviderAdapter):
    async def validate(self, api_key: str) -> bool:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(_MODEL_NAME)
            await model.generate_content_async(
                "hi", generation_config={"max_output_tokens": 5}
            )
            return True
        except (PermissionDenied, Unauthenticated, InvalidArgument):
            # Google reports a malformed/unknown API key as InvalidArgument
            # ("API key not valid"), not as an auth error.
            return False
        except ResourceExhausted as exc:
            raise ProviderRateLimitError(str(exc)) from exc

    async def chat(
        self, api_key: str, messages: list[Message], stream: bool = True
    ) -> AsyncIterator[str]:
        genai.configure(api_key=api_key)
        system_instruction, contents = _to_gemini_contents(messages)
        model = genai.GenerativeModel(_MODEL_NAME, system_instruction=system_instruction)

        try:
            if stream:
                response = await model.generate_content_async(contents, stream=True)
                async for chunk in response:
                    if chunk.text:
                        yield chunk.text
            else:
                response = await model.generate_content_async(contents)
                yield response.text
        except (PermissionDenied, Unauthenticated) as exc:
            raise ProviderAuthError(str(exc)) from exc
        except ResourceExhausted as exc:
            raise ProviderRateLimitError(str(exc)) from exc

    async def embed(self, api_key: str, text: str) -> list[float]:
        genai.configure(api_key=api_key)
        try:
            result = await asyncio.to_thread(
                genai.embed_content,
                model=_EMBEDDING_MODEL,
                content=text,
                output_dimensionality=EMBEDDING_DIMENSIONS,
            )
            return result["embedding"]
        except (PermissionDenied, Unauthenticated) as exc:
            raise ProviderAuthError(str(exc)) from exc
        except ResourceExhausted as exc:
            raise ProviderRateLimitError(str(exc)) from exc
