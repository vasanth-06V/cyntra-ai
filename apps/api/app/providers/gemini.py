"""Gemini adapter over the public REST API (no SDK).

Why not the SDK: the legacy `google-generativeai` package is deprecated, the
replacement pins an httpx version that conflicts with supabase-py, and the
old one forced a private-attribute hack to avoid cross-user key mixing. Plain
httpx gives us explicit per-request keys (a header, never a URL), real
timeouts, access to the raw error bodies (retry hints, quota type) and
thinking control -- and it is trivially testable with httpx.MockTransport.

Every provider failure is mapped to one of the typed errors in providers/base.
"""

import asyncio
import json
import logging
import math
import time
from collections.abc import AsyncIterator

import httpx

from app.llm.models import (
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    gemini_traits,
    model_for,
    timeout_for,
)
from app.llm.options import LLMOptions, Usage
from app.providers.base import (
    Message,
    MessageRole,
    ProviderAdapter,
    ProviderAuthError,
    ProviderBadRequestError,
    ProviderBlockedError,
    ProviderConfigError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
_EMBED_BATCH_SIZE = 100
_EMBED_TASK_TYPES = {"doc": "RETRIEVAL_DOCUMENT", "query": "RETRIEVAL_QUERY"}

_FINISH_REASONS = {
    "STOP": "stop",
    "MAX_TOKENS": "length",
    "SAFETY": "blocked",
    "RECITATION": "blocked",
    "BLOCKLIST": "blocked",
    "PROHIBITED_CONTENT": "blocked",
    "SPII": "blocked",
    "LANGUAGE": "blocked",
    "IMAGE_SAFETY": "blocked",
}

# Models for which the API rejected thinkingConfig; we stop sending it (the
# value was a best guess that live smoke-testing has yet to confirm).
_thinking_rejected: set[str] = set()


# --- request building -------------------------------------------------------


def _to_gemini_contents(messages: list[Message]) -> tuple[str | None, list[dict]]:
    """Gemini has no 'system' role on messages -- system instructions are sent
    separately. Several system messages are joined rather than the last one
    silently winning. Returns (system_instruction, contents)."""
    system_parts: list[str] = []
    contents: list[dict] = []
    for m in messages:
        if m.role == MessageRole.SYSTEM:
            system_parts.append(m.content)
            continue
        role = "model" if m.role == MessageRole.ASSISTANT else "user"
        contents.append({"role": role, "parts": [{"text": m.content}]})
    return ("\n\n".join(system_parts) or None), contents


def _build_body(
    messages: list[Message], options: LLMOptions, model: str, with_thinking: bool
) -> dict:
    system, contents = _to_gemini_contents(messages)
    traits = gemini_traits(model)

    config: dict = {}
    if options.max_output_tokens is not None:
        # Thought tokens share this budget, so leave room for them.
        config["maxOutputTokens"] = options.max_output_tokens + traits["allowance"]
    if options.temperature is not None:
        config["temperature"] = options.temperature
    if options.json_mode:
        config["responseMimeType"] = "application/json"
    if with_thinking and traits["thinking_config"] and model not in _thinking_rejected:
        config["thinkingConfig"] = dict(traits["thinking_config"])

    body: dict = {"contents": contents}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    if config:
        body["generationConfig"] = config
    return body


# --- response parsing -------------------------------------------------------


def _text_of(candidate: dict) -> str:
    parts = (candidate.get("content") or {}).get("parts") or []
    return "".join(p.get("text", "") for p in parts if not p.get("thought"))


def _apply_usage(usage: Usage | None, metadata: dict | None) -> None:
    if usage is None or not metadata:
        return
    usage.input_tokens = metadata.get("promptTokenCount", usage.input_tokens) or 0
    usage.output_tokens = metadata.get("candidatesTokenCount", usage.output_tokens) or 0
    usage.thought_tokens = metadata.get("thoughtsTokenCount", usage.thought_tokens) or 0
    usage.cached_tokens = metadata.get("cachedContentTokenCount", usage.cached_tokens) or 0


def _finish_of(candidate: dict, data: dict) -> str | None:
    raw = candidate.get("finishReason")
    if raw:
        return _FINISH_REASONS.get(raw, "other")
    if (data.get("promptFeedback") or {}).get("blockReason"):
        return "blocked"
    return None


def _parse_seconds(value) -> float | None:
    """Google writes durations as strings like "30s" or "0.5s"."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.endswith("s"):
        try:
            return float(value[:-1])
        except ValueError:
            return None
    return None


# --- error mapping ----------------------------------------------------------


def _error_parts(body: bytes | str | None) -> tuple[str, str, list]:
    """(message, status, details) from a Google error body; tolerant of junk."""
    try:
        data = json.loads(body or b"{}")
        error = data.get("error", {}) if isinstance(data, dict) else {}
        return (
            str(error.get("message", "")),
            str(error.get("status", "")),
            error.get("details") or [],
        )
    except (ValueError, AttributeError):
        text = body.decode("utf-8", "replace") if isinstance(body, bytes) else str(body or "")
        return text[:300], "", []


def _quota_kind(message: str, details: list) -> str:
    haystack = message.lower()
    for detail in details:
        if isinstance(detail, dict) and str(detail.get("@type", "")).endswith("QuotaFailure"):
            haystack += " " + json.dumps(detail.get("violations", [])).lower()
    if "perday" in haystack or "per day" in haystack or "daily" in haystack:
        return "rpd"
    if "perminute" in haystack or "per minute" in haystack:
        return "rpm"
    return "unknown"


def _retry_after(details: list, headers: httpx.Headers | None) -> float | None:
    for detail in details:
        if isinstance(detail, dict) and str(detail.get("@type", "")).endswith("RetryInfo"):
            seconds = _parse_seconds(detail.get("retryDelay"))
            if seconds is not None:
                return seconds
    header = headers.get("retry-after") if headers else None
    try:
        return float(header) if header else None
    except ValueError:
        return None


def map_error(status: int, body: bytes | str | None, headers: httpx.Headers | None = None) -> Exception:
    """Turns a non-2xx Google response into the right typed error."""
    message, google_status, details = _error_parts(body)
    lowered = message.lower()
    reasons = {
        str(d.get("reason", ""))
        for d in details
        if isinstance(d, dict) and str(d.get("@type", "")).endswith("ErrorInfo")
    }

    if status == 400:
        if "API_KEY_INVALID" in reasons or ("api key" in lowered and "valid" in lowered):
            return ProviderAuthError(message or "API key not valid")
        return ProviderBadRequestError(message or "Bad request")
    if status in (401, 403):
        return ProviderAuthError(message or "Not permitted")
    if status == 404:
        return ProviderConfigError(message or "Model not found")
    if status == 429:
        return ProviderRateLimitError(
            message or "Quota exceeded",
            kind=_quota_kind(message, details),
            retry_after=_retry_after(details, headers),
        )
    if status == 408 or status == 504:
        return ProviderUnavailableError(message or "Timed out", _retry_after(details, headers))
    if status >= 500:
        return ProviderUnavailableError(message or f"Server error {status}", _retry_after(details, headers))
    return ProviderBadRequestError(f"Unexpected status {status}: {message}")


def _thinking_complaint(error: Exception) -> bool:
    return isinstance(error, ProviderBadRequestError) and "thinking" in str(error).lower()


# --- the adapter ------------------------------------------------------------


def _l2_normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vector))
    return [x / norm for x in vector] if norm > 0 else vector


class GeminiAdapter(ProviderAdapter):
    name = "gemini"

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None):
        self._transport = transport
        self._clients: dict[int, tuple[asyncio.AbstractEventLoop, httpx.AsyncClient]] = {}

    def _http(self) -> httpx.AsyncClient:
        """One pooled client per event loop (an AsyncClient is bound to the
        loop that first used it)."""
        loop = asyncio.get_running_loop()
        entry = self._clients.get(id(loop))
        if entry and entry[0] is loop and not entry[1].is_closed:
            return entry[1]
        client = httpx.AsyncClient(
            transport=self._transport,
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        )
        self._clients[id(loop)] = (loop, client)
        return client

    @staticmethod
    def _headers(api_key: str) -> dict:
        # Key in a header, not the URL: URLs end up in logs and proxies.
        return {"x-goog-api-key": api_key, "content-type": "application/json"}

    async def _request(self, method: str, url: str, api_key: str, timeout: float, **kwargs) -> httpx.Response:
        try:
            return await self._http().request(
                method, url, headers=self._headers(api_key), timeout=timeout, **kwargs
            )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(f"Gemini did not answer within {timeout:.0f}s") from exc
        except httpx.TransportError as exc:
            raise ProviderUnavailableError(f"Could not reach Gemini: {type(exc).__name__}") from exc

    # -- validate

    async def validate(self, api_key: str) -> bool:
        """Lists models instead of generating text: it checks the key without
        spending any of the daily generation quota."""
        response = await self._request(
            "GET", f"{BASE_URL}/models", api_key, timeout_for("validate"), params={"pageSize": 1}
        )
        if response.status_code == 200:
            return True
        error = map_error(response.status_code, response.content, response.headers)
        if isinstance(error, (ProviderAuthError, ProviderBadRequestError)) and response.status_code in (400, 401, 403):
            return False  # Google reports a bad/malformed key as 400 "API key not valid"
        raise error

    # -- chat

    async def chat(
        self,
        api_key: str,
        messages: list[Message],
        stream: bool = True,
        options: LLMOptions | None = None,
        usage: Usage | None = None,
    ) -> AsyncIterator[str]:
        options = options or LLMOptions()
        model = options.model_override or model_for(self.name, options.task)
        timeout = options.timeout_s or timeout_for(options.task)
        if usage is not None:
            usage.model = model

        if stream:
            async for text in self._stream(api_key, messages, options, model, timeout, usage):
                yield text
        else:
            yield await self._generate(api_key, messages, options, model, timeout, usage)

    async def _generate(self, api_key, messages, options, model, timeout, usage) -> str:
        url = f"{BASE_URL}/models/{model}:generateContent"
        for with_thinking in (True, False):
            body = _build_body(messages, options, model, with_thinking)
            response = await self._request("POST", url, api_key, timeout, json=body)
            if response.status_code == 200:
                break
            error = map_error(response.status_code, response.content, response.headers)
            if with_thinking and "thinkingConfig" in body.get("generationConfig", {}) and _thinking_complaint(error):
                _thinking_rejected.add(model)
                logger.warning("Gemini rejected thinkingConfig for %s; continuing without it", model)
                continue
            raise error

        data = response.json()
        candidate = (data.get("candidates") or [{}])[0]
        text = _text_of(candidate)
        finish = _finish_of(candidate, data)
        _apply_usage(usage, data.get("usageMetadata"))
        if usage is not None:
            usage.requests += 1
            usage.finish_reason = finish
        if not text and finish == "blocked":
            raise ProviderBlockedError("Gemini returned no text (blocked)")
        return text

    async def _stream(self, api_key, messages, options, model, timeout, usage) -> AsyncIterator[str]:
        url = f"{BASE_URL}/models/{model}:streamGenerateContent"
        started = time.perf_counter()
        yielded = False
        finish: str | None = None
        blocked = False

        for with_thinking in (True, False):
            body = _build_body(messages, options, model, with_thinking)
            try:
                async with self._http().stream(
                    "POST",
                    url,
                    params={"alt": "sse"},
                    headers=self._headers(api_key),
                    json=body,
                    timeout=httpx.Timeout(timeout, connect=10.0),
                ) as response:
                    if response.status_code != 200:
                        error = map_error(response.status_code, await response.aread(), response.headers)
                        if with_thinking and "thinkingConfig" in body.get("generationConfig", {}) and _thinking_complaint(error):
                            _thinking_rejected.add(model)
                            logger.warning("Gemini rejected thinkingConfig for %s; continuing without it", model)
                            continue
                        raise error

                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        payload = line[5:].strip()
                        if not payload or payload == "[DONE]":
                            continue
                        chunk = json.loads(payload)
                        candidate = (chunk.get("candidates") or [{}])[0]
                        text = _text_of(candidate)
                        finish = _finish_of(candidate, chunk) or finish
                        blocked = blocked or bool((chunk.get("promptFeedback") or {}).get("blockReason"))
                        _apply_usage(usage, chunk.get("usageMetadata"))
                        if text:
                            if not yielded and usage is not None:
                                usage.ttft_ms = round((time.perf_counter() - started) * 1000, 1)
                            yielded = True
                            yield text
                break
            except httpx.TimeoutException as exc:
                raise ProviderTimeoutError(f"Gemini stream stalled for {timeout:.0f}s") from exc
            except httpx.TransportError as exc:
                raise ProviderUnavailableError(f"Gemini connection dropped: {type(exc).__name__}") from exc

        if usage is not None:
            usage.requests += 1
            usage.finish_reason = finish
        if not yielded and (finish == "blocked" or blocked):
            raise ProviderBlockedError("Gemini returned no text (blocked)")

    # -- embeddings

    async def embed_many(
        self,
        api_key: str,
        texts: list[str],
        usage: Usage | None = None,
        kind: str = "doc",
    ) -> list[list[float]]:
        """One request per 100 texts (instead of one per text). Vectors come
        back L2-normalized: Google only pre-normalizes the full 3072-d output,
        and ours are truncated to EMBEDDING_DIMENSIONS."""
        if not texts:
            return []
        task_type = _EMBED_TASK_TYPES.get(kind, "RETRIEVAL_DOCUMENT")
        url = f"{BASE_URL}/{EMBEDDING_MODEL}:batchEmbedContents"

        vectors: list[list[float]] = []
        for start in range(0, len(texts), _EMBED_BATCH_SIZE):
            batch = texts[start : start + _EMBED_BATCH_SIZE]
            body = {
                "requests": [
                    {
                        "model": EMBEDDING_MODEL,
                        "content": {"parts": [{"text": t}]},
                        "taskType": task_type,
                        "outputDimensionality": EMBEDDING_DIMENSIONS,
                    }
                    for t in batch
                ]
            }
            response = await self._request("POST", url, api_key, 30.0, json=body)
            if response.status_code != 200:
                raise map_error(response.status_code, response.content, response.headers)
            embeddings = response.json().get("embeddings") or []
            if len(embeddings) != len(batch):
                raise ProviderBadRequestError(
                    f"Embedding count mismatch: sent {len(batch)} texts, got {len(embeddings)} vectors"
                )
            vectors.extend(_l2_normalize(e["values"]) for e in embeddings)
            if usage is not None:
                usage.requests += 1
        return vectors
