import pytest
from fastapi import HTTPException

from app.chat import service
from app.providers.base import ProviderRateLimitError


class FakeAdapter:
    """Yields canned chunks for the primary key, raises
    ProviderRateLimitError for a configured number of calls before
    succeeding (or never, if always_fails=True)."""

    def __init__(self, fail_before_backup: bool = False, always_fails: bool = False):
        self.fail_before_backup = fail_before_backup
        self.always_fails = always_fails
        self.calls: list[str] = []

    async def chat(self, api_key, messages, stream=True):
        self.calls.append(api_key)
        if api_key == "primary-key" and (self.fail_before_backup or self.always_fails):
            raise ProviderRateLimitError("rate limited")
        if api_key == "backup-key" and self.always_fails:
            raise ProviderRateLimitError("rate limited")
        for chunk in ["Hello", ", ", "world!"]:
            yield chunk


@pytest.fixture(autouse=True)
def _common_mocks(monkeypatch):
    monkeypatch.setattr(service, "decrypt_key", lambda encrypted: encrypted)
    monkeypatch.setattr(
        service, "_require_owned_conversation", lambda *a, **kw: _async_none()
    )
    monkeypatch.setattr(service, "list_messages", lambda *a, **kw: _async_value([]))

    appended = []

    async def fake_append(conversation_id, role, content, provider=None):
        appended.append({"role": role, "content": content, "provider": provider})
        return {}

    monkeypatch.setattr(service, "_append_message", fake_append)
    return appended


async def _async_none():
    return None


async def _async_value(value):
    return value


def _key_row(label: str) -> dict:
    return {"id": label, "encrypted_key": label}


async def _collect(agen):
    return [chunk async for chunk in agen]


@pytest.mark.asyncio
async def test_streams_full_reply_on_primary_key(monkeypatch, _common_mocks):
    adapter = FakeAdapter()
    monkeypatch.setattr(service, "get_adapter", lambda provider: adapter)

    async def fake_get_key_row(user_id, provider, slot):
        return _key_row("primary-key") if slot == "primary" else None

    monkeypatch.setattr(service, "get_key_row", fake_get_key_row)

    chunks = await _collect(service.stream_reply("user-1", "conv-1", "gemini", "hi"))

    assert "".join(chunks) == "Hello, world!"
    assert adapter.calls == ["primary-key"]
    assert _common_mocks[-1] == {
        "role": "assistant",
        "content": "Hello, world!",
        "provider": "gemini",
    }


@pytest.mark.asyncio
async def test_fails_over_to_backup_before_any_chunk_sent(monkeypatch, _common_mocks):
    adapter = FakeAdapter(fail_before_backup=True)
    monkeypatch.setattr(service, "get_adapter", lambda provider: adapter)

    async def fake_get_key_row(user_id, provider, slot):
        return _key_row(f"{slot}-key")

    notified = {}

    async def fake_notify(user_id, message):
        notified["message"] = message

    monkeypatch.setattr(service, "get_key_row", fake_get_key_row)
    monkeypatch.setattr(service, "notify_user", fake_notify)

    chunks = await _collect(service.stream_reply("user-1", "conv-1", "gemini", "hi"))

    assert "".join(chunks) == "Hello, world!"
    assert adapter.calls == ["primary-key", "backup-key"]
    assert "switched to your backup key" in notified["message"]


@pytest.mark.asyncio
async def test_raises_412_when_no_key_configured_at_all(monkeypatch, _common_mocks):
    adapter = FakeAdapter()
    monkeypatch.setattr(service, "get_adapter", lambda provider: adapter)

    async def fake_get_key_row(user_id, provider, slot):
        return None

    monkeypatch.setattr(service, "get_key_row", fake_get_key_row)

    with pytest.raises(HTTPException) as exc_info:
        await _collect(service.stream_reply("user-1", "conv-1", "gemini", "hi"))

    assert exc_info.value.status_code == 412


@pytest.mark.asyncio
async def test_raises_429_when_rate_limited_and_no_backup(monkeypatch, _common_mocks):
    adapter = FakeAdapter(fail_before_backup=True)
    monkeypatch.setattr(service, "get_adapter", lambda provider: adapter)

    async def fake_get_key_row(user_id, provider, slot):
        return _key_row("primary-key") if slot == "primary" else None

    monkeypatch.setattr(service, "get_key_row", fake_get_key_row)

    with pytest.raises(HTTPException) as exc_info:
        await _collect(service.stream_reply("user-1", "conv-1", "gemini", "hi"))

    assert exc_info.value.status_code == 429
