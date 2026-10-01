from collections.abc import Sequence

from app.keys.service import call_with_failover
from app.providers.base import Message
from app.providers.registry import get_adapter


async def complete_text(user_id: str, provider: str, messages: Sequence[Message]) -> str:
    """A one-shot (non-streaming) LLM call, going through call_with_failover
    since it fits the one-shot-call shape that helper expects (unlike chat's
    streaming replies, which need their own failover handling)."""
    adapter = get_adapter(provider)

    async def _call(api_key: str) -> str:
        chunks = []
        async for chunk in adapter.chat(api_key, list(messages), stream=False):
            chunks.append(chunk)
        return "".join(chunks)

    return await call_with_failover(user_id, provider, _call)
