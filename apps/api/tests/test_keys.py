import pytest

from app.keys import service
from app.keys.service import BothKeysFailedError, call_with_failover
from app.providers.base import ProviderRateLimitError


@pytest.fixture(autouse=True)
def _patch_decrypt(monkeypatch):
    # Tests exercise the failover control flow, not real encryption --
    # identity-map "encrypted" -> "decrypted" so no real Fernet key is needed.
    monkeypatch.setattr(service, "decrypt_key", lambda encrypted: encrypted)


def _key_row(label: str) -> dict:
    return {"id": label, "encrypted_key": label}


@pytest.mark.asyncio
async def test_succeeds_on_primary_key(monkeypatch):
    async def fake_get_key_row(user_id, provider, slot):
        return _key_row("primary-key") if slot == "primary" else None

    monkeypatch.setattr(service, "get_key_row", fake_get_key_row)

    async def fn(api_key: str) -> str:
        assert api_key == "primary-key"
        return "ok"

    result = await call_with_failover("user-1", "gemini", fn)
    assert result == "ok"


@pytest.mark.asyncio
async def test_fails_over_to_backup_on_rate_limit_and_notifies(monkeypatch):
    async def fake_get_key_row(user_id, provider, slot):
        return _key_row(f"{slot}-key")

    notified = {}

    async def fake_notify_user(user_id, message):
        notified["user_id"] = user_id
        notified["message"] = message

    monkeypatch.setattr(service, "get_key_row", fake_get_key_row)
    monkeypatch.setattr(service, "notify_user", fake_notify_user)

    calls = []

    async def fn(api_key: str) -> str:
        calls.append(api_key)
        if api_key == "primary-key":
            raise ProviderRateLimitError("rate limited")
        return "backup result"

    result = await call_with_failover("user-1", "gemini", fn)

    assert result == "backup result"
    assert calls == ["primary-key", "backup-key"]
    assert notified["user_id"] == "user-1"
    assert "switched to your backup key" in notified["message"]


@pytest.mark.asyncio
async def test_raises_when_primary_rate_limited_and_no_backup_configured(monkeypatch):
    async def fake_get_key_row(user_id, provider, slot):
        return _key_row("primary-key") if slot == "primary" else None

    monkeypatch.setattr(service, "get_key_row", fake_get_key_row)

    async def fn(api_key: str) -> str:
        raise ProviderRateLimitError("rate limited")

    with pytest.raises(BothKeysFailedError, match="no backup key is configured"):
        await call_with_failover("user-1", "gemini", fn)


@pytest.mark.asyncio
async def test_raises_when_both_keys_rate_limited(monkeypatch):
    async def fake_get_key_row(user_id, provider, slot):
        return _key_row(f"{slot}-key")

    async def fake_notify_user(user_id, message):
        pytest.fail("should not notify when both keys fail")

    monkeypatch.setattr(service, "get_key_row", fake_get_key_row)
    monkeypatch.setattr(service, "notify_user", fake_notify_user)

    async def fn(api_key: str) -> str:
        raise ProviderRateLimitError("rate limited")

    with pytest.raises(BothKeysFailedError, match="Both primary and backup"):
        await call_with_failover("user-1", "gemini", fn)


@pytest.mark.asyncio
async def test_raises_when_no_primary_key_configured(monkeypatch):
    async def fake_get_key_row(user_id, provider, slot):
        return None

    monkeypatch.setattr(service, "get_key_row", fake_get_key_row)

    async def fn(api_key: str) -> str:
        pytest.fail("fn should never be called when no primary key exists")

    with pytest.raises(BothKeysFailedError, match="No gemini key configured"):
        await call_with_failover("user-1", "gemini", fn)
