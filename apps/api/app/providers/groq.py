from collections.abc import AsyncIterator

from groq import AsyncGroq
from groq import AuthenticationError, RateLimitError

from app.providers.base import Message, ProviderAdapter, ProviderAuthError, ProviderRateLimitError

_VALIDATE_MODEL = "llama-3.1-8b-instant"
_CHAT_MODEL = "llama-3.3-70b-versatile"


class GroqAdapter(ProviderAdapter):
    async def validate(self, api_key: str) -> bool:
        client = AsyncGroq(api_key=api_key)
        try:
            await client.chat.completions.create(
                model=_VALIDATE_MODEL,
                max_tokens=5,
                messages=[{"role": "user", "content": "hi"}],
            )
            return True
        except AuthenticationError:
            return False
        except RateLimitError as exc:
            raise ProviderRateLimitError(str(exc)) from exc

    async def chat(
        self, api_key: str, messages: list[Message], stream: bool = True
    ) -> AsyncIterator[str]:
        client = AsyncGroq(api_key=api_key)
        converted = [{"role": m.role.value, "content": m.content} for m in messages]

        try:
            if stream:
                response = await client.chat.completions.create(
                    model=_CHAT_MODEL, messages=converted, stream=True
                )
                async for chunk in response:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        yield delta
            else:
                response = await client.chat.completions.create(
                    model=_CHAT_MODEL, messages=converted
                )
                yield response.choices[0].message.content or ""
        except AuthenticationError as exc:
            raise ProviderAuthError(str(exc)) from exc
        except RateLimitError as exc:
            raise ProviderRateLimitError(str(exc)) from exc

    # No embed() override -- Groq has no embeddings API (see base.py).
