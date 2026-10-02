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


class ProviderError(Exception):
    """Base for everything an adapter raises on purpose. The gateway maps each
    subclass to one user-facing outcome; nothing below leaks a raw SDK or HTTP
    error to a caller."""


class ProviderRateLimitError(ProviderError):
    """The provider reports a rate-limit or quota error. llm.gateway catches
    this specifically to trigger the primary -> backup key failover.

    kind: "rpm" (per-minute: waiting helps), "rpd" (daily quota: the key is
    spent until the reset), or "unknown". retry_after is the provider's own
    hint in seconds, when it gave one."""

    def __init__(self, message: str = "", kind: str = "unknown", retry_after: float | None = None):
        super().__init__(message)
        self.kind = kind
        self.retry_after = retry_after


class ProviderUnavailableError(ProviderError):
    """The provider is temporarily overloaded or erroring (HTTP 5xx-style,
    e.g. "model is currently experiencing high demand"). Distinct from a rate
    limit (the user's key hit its quota -> try the backup key): here the
    *provider* is struggling, so the right response is a short retry, then a
    clear "try again" message."""

    def __init__(self, message: str = "", retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class ProviderTimeoutError(ProviderError):
    """The call did not finish within its deadline."""


class ProviderAuthError(ProviderError):
    """The provider rejects the key itself (invalid/revoked/not permitted)."""


class ProviderBadRequestError(ProviderError):
    """The provider rejected *our request* (oversized prompt, unsupported
    parameter...). A bug or limit on our side, not the user's key: retrying
    won't help and the user should see a generic message, not 'key rejected'."""


class ProviderConfigError(ProviderError):
    """Our configuration is stale -- typically a retired/unknown model name.
    Never retried; logged loudly because only a deploy fixes it."""


class ProviderBlockedError(ProviderError):
    """The provider declined to answer (e.g. Gemini's safety filter returned
    no text). Retrying or switching keys won't help; the caller gets a clear
    error instead of an opaque 500."""


def retry_after_from(exc: Exception) -> float | None:
    """The provider's Retry-After header (seconds) on an SDK status error, if any."""
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    value = headers.get("retry-after") if headers else None
    try:
        return float(value) if value else None
    except (TypeError, ValueError):
        return None


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
        self,
        api_key: str,
        texts: list[str],
        usage: Usage | None = None,
        kind: str = "doc",
    ) -> list[list[float]]:
        """Embeds a whole list in as few requests as the provider allows.
        Only the Gemini adapter implements this -- the RAG layer always
        routes embeddings through Gemini regardless of the user's chat
        provider (Section 6.1 of the plan)."""
        raise NotImplementedError(f"{type(self).__name__} does not support embeddings")

    async def embed(self, api_key: str, text: str) -> list[float]:
        return (await self.embed_many(api_key, [text]))[0]
