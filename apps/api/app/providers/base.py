from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import Enum

from app.llm.options import LLMOptions, Usage


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class Message:
    role: MessageRole
    content: str


class ProviderRateLimitError(Exception):
    """Raised by an adapter when the provider reports a rate-limit or quota
    error. llm.gateway catches this specifically to
    trigger the primary -> backup key failover."""


class ProviderUnavailableError(Exception):
    """The provider is temporarily overloaded or erroring (HTTP 5xx-style,
    e.g. Gemini's "model is currently experiencing high demand"). Distinct
    from a rate limit (the user's key hit its quota -> try the backup key):
    here the *provider* is struggling, so the right response is a short
    retry, then a clear "try again" message."""


class ProviderAuthError(Exception):
    """Raised when the provider rejects the key itself (invalid/revoked)."""


class ProviderBlockedError(Exception):
    """The provider declined to answer (e.g. Gemini's safety filter returned
    no text). Retrying or switching keys won't help; the caller gets a clear
    error instead of an opaque 500."""


class ProviderAdapter(ABC):
    """Common interface every LLM provider module implements, so
    orchestration code (chat, interviews, ATS scoring) never has to branch
    on provider identity directly."""

    # Provider key used to look the model up in llm.models.
    name: str

    @abstractmethod
    async def validate(self, api_key: str) -> bool:
        """Cheaply confirms the key works. Returns False for an invalid key;
        raises ProviderRateLimitError if the provider itself is rate-limited
        (distinct from an invalid key)."""

    @abstractmethod
    async def chat(
        self,
        api_key: str,
        messages: list[Message],
        stream: bool = True,
        options: LLMOptions | None = None,
        usage: Usage | None = None,
    ) -> AsyncIterator[str]:
        """Yields response text chunks. If `usage` is given it is filled with
        the provider-reported token counts once the response completes."""

    async def embed_many(
        self, api_key: str, texts: list[str], usage: Usage | None = None
    ) -> list[list[float]]:
        """Embeds a whole list in as few requests as the provider allows.
        Only the Gemini adapter implements this -- the RAG layer always
        routes embeddings through Gemini regardless of the user's chat
        provider (Section 6.1 of the plan)."""
        raise NotImplementedError(f"{type(self).__name__} does not support embeddings")

    async def embed(self, api_key: str, text: str) -> list[float]:
        return (await self.embed_many(api_key, [text]))[0]
