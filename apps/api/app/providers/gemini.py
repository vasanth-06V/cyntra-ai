import asyncio
from collections.abc import AsyncIterator

import google.generativeai as genai
from google.api_core.exceptions import PermissionDenied, ResourceExhausted, Unauthenticated

from app.providers.base import Message, MessageRole, ProviderAdapter, ProviderAuthError, ProviderRateLimitError

_MODEL_NAME = "gemini-1.5-flash"
_EMBEDDING_MODEL = "models/text-embedding-004"


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
        except (PermissionDenied, Unauthenticated):
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
                genai.embed_content, model=_EMBEDDING_MODEL, content=text
            )
            return result["embedding"]
        except (PermissionDenied, Unauthenticated) as exc:
            raise ProviderAuthError(str(exc)) from exc
        except ResourceExhausted as exc:
            raise ProviderRateLimitError(str(exc)) from exc
