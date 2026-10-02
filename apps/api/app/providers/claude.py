from collections.abc import AsyncIterator

from anthropic import AsyncAnthropic
from anthropic import AuthenticationError, RateLimitError

from app.providers.base import Message, MessageRole, ProviderAdapter, ProviderAuthError, ProviderRateLimitError

_VALIDATE_MODEL = "claude-haiku-4-5-20251001"
_CHAT_MODEL = "claude-sonnet-5"


def _to_anthropic_messages(messages: list[Message]) -> tuple[str | None, list[dict]]:
    system = None
    converted: list[dict] = []
    for m in messages:
        if m.role == MessageRole.SYSTEM:
            system = m.content
            continue
        converted.append({"role": m.role.value, "content": m.content})
    return system, converted


class ClaudeAdapter(ProviderAdapter):
    async def validate(self, api_key: str) -> bool:
        client = AsyncAnthropic(api_key=api_key)
        try:
            await client.messages.create(
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
        client = AsyncAnthropic(api_key=api_key)
        system, converted = _to_anthropic_messages(messages)

        try:
            if stream:
                async with client.messages.stream(
                    model=_CHAT_MODEL,
                    max_tokens=4096,
                    system=system,
                    messages=converted,
                ) as response_stream:
                    async for text in response_stream.text_stream:
                        yield text
            else:
                response = await client.messages.create(
                    model=_CHAT_MODEL,
                    max_tokens=4096,
                    system=system,
                    messages=converted,
                )
                yield "".join(block.text for block in response.content if block.type == "text")
        except AuthenticationError as exc:
            raise ProviderAuthError(str(exc)) from exc
        except RateLimitError as exc:
            raise ProviderRateLimitError(str(exc)) from exc

    # No embed() override -- Claude has no embeddings API (see base.py).
