from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import Enum


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
    error. keys.service.call_with_failover catches this specifically to
    trigger the primary -> backup key failover."""


class ProviderAuthError(Exception):
    """Raised when the provider rejects the key itself (invalid/revoked)."""


class ProviderAdapter(ABC):
    """Common interface every LLM provider module implements, so
    orchestration code (chat, interviews, ATS scoring) never has to branch
    on provider identity directly."""

    @abstractmethod
    async def validate(self, api_key: str) -> bool:
        """Sends a minimal request to confirm the key works. Returns False
        for an invalid key; raises ProviderRateLimitError if the provider
        itself is rate-limited (distinct from an invalid key)."""

    @abstractmethod
    async def chat(
        self, api_key: str, messages: list[Message], stream: bool = True
    ) -> AsyncIterator[str]:
        """Yields response text chunks."""

    async def embed(self, api_key: str, text: str) -> list[float]:
        """Only meaningfully implemented by the Gemini adapter -- the RAG
        layer always routes embedding calls through Gemini regardless of
        the user's chat-provider choice (see Section 6.1 of the plan)."""
        raise NotImplementedError(
            f"{type(self).__name__} does not support embeddings"
        )
