"""BYOK key endpoints end to end (POST/GET/DELETE /keys)."""

import logging

import pytest

from app.core.security import decrypt_key
from app.providers.base import ProviderUnavailableError

from .conftest import USER_A, USER_B, as_user, seed_key


async def test_submit_valid_key_stores_encrypted_and_returns_no_secret(client, env):
    r = await client.post(
        "/keys",
        json={"provider": "gemini", "slot": "primary", "api_key": "AIza-secret-123"},
        headers=as_user(USER_A),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["is_valid"] is True and body["provider"] == "gemini" and body["slot"] == "primary"
    assert "AIza-secret-123" not in r.text
    assert "encrypted_key" not in body and "api_key" not in body

    stored = env.db.rows("provider_keys", user_id=USER_A)[0]
    assert stored["encrypted_key"] != "AIza-secret-123"
    assert decrypt_key(stored["encrypted_key"]) == "AIza-secret-123"
    assert env.gemini.validate_calls == ["AIza-secret-123"]


async def test_invalid_key_is_rejected_400_and_nothing_is_stored(client, env):
    env.gemini.invalid_keys.add("bad-key-123")
    r = await client.post(
        "/keys", json={"provider": "gemini", "slot": "primary", "api_key": "bad-key-123"},
        headers=as_user(USER_A),
    )
    assert r.status_code == 400 and "Nothing was saved" in r.json()["detail"]
    assert env.db.rows("provider_keys") == []


async def test_rate_limited_validation_is_429_and_nothing_is_stored(client, env):
    env.gemini.rate_limited_keys.add("key-12345")
    r = await client.post(
        "/keys", json={"provider": "gemini", "slot": "primary", "api_key": "key-12345"},
        headers=as_user(USER_A),
    )
    assert r.status_code == 429
    assert env.db.rows("provider_keys") == []


async def test_provider_outage_during_validation_is_503_and_nothing_is_stored(client, env):
    env.gemini.validate_error = ProviderUnavailableError("503 high demand")
    r = await client.post(
        "/keys", json={"provider": "gemini", "slot": "primary", "api_key": "key-12345"},
        headers=as_user(USER_A),
    )
    assert r.status_code == 503
    assert env.db.rows("provider_keys") == []


async def test_failed_resubmit_never_destroys_a_working_key(client, env):
    seed_key(env, USER_A, "gemini", "primary", "good-key", valid=True)
    env.gemini.invalid_keys.add("typo-key")
    r = await client.post(
        "/keys", json={"provider": "gemini", "slot": "primary", "api_key": "typo-key"},
        headers=as_user(USER_A),
    )
    assert r.status_code == 400
    row = env.db.rows("provider_keys", user_id=USER_A)[0]
    assert decrypt_key(row["encrypted_key"]) == "good-key" and row["is_valid"] is True


async def test_resubmitting_same_slot_overwrites_instead_of_duplicating(client, env):
    for raw in ("first-key-1", "second-key-1"):
        r = await client.post(
            "/keys", json={"provider": "groq", "slot": "backup", "api_key": raw},
            headers=as_user(USER_A),
        )
        assert r.status_code == 201
    rows = env.db.rows("provider_keys", user_id=USER_A, provider="groq", slot="backup")
    assert len(rows) == 1 and decrypt_key(rows[0]["encrypted_key"]) == "second-key-1"


async def test_list_returns_only_my_keys_without_secrets(client, env):
    seed_key(env, USER_A, "gemini", "primary", "a-secret")
    seed_key(env, USER_B, "gemini", "primary", "b-secret")

    r = await client.get("/keys", headers=as_user(USER_A))
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert set(data[0]) == {"id", "provider", "slot", "is_valid", "last_validated_at"}
    assert "a-secret" not in r.text and "b-secret" not in r.text


async def test_delete_removes_own_key(client, env):
    row = seed_key(env, USER_A, "gemini", "primary", "x")
    r = await client.delete(f"/keys/{row['id']}", headers=as_user(USER_A))
    assert r.status_code == 204
    assert env.db.rows("provider_keys") == []


async def test_cannot_delete_another_users_key(client, env):
    row = seed_key(env, USER_B, "gemini", "primary", "x")
    r = await client.delete(f"/keys/{row['id']}", headers=as_user(USER_A))
    assert r.status_code == 204  # silently a no-op ...
    assert len(env.db.rows("provider_keys", user_id=USER_B)) == 1  # ... and B's key survives


async def test_unknown_provider_or_slot_is_rejected_with_422(client, env):
    for body in (
        {"provider": "openai", "slot": "primary", "api_key": "key-12345"},
        {"provider": "gemini", "slot": "tertiary", "api_key": "key-12345"},
        {"provider": "gemini", "slot": "primary"},
    ):
        r = await client.post("/keys", json=body, headers=as_user(USER_A))
        assert r.status_code == 422


async def test_key_plaintext_never_appears_in_logs(client, env, caplog):
    caplog.set_level(logging.DEBUG)
    await client.post(
        "/keys", json={"provider": "gemini", "slot": "primary", "api_key": "AIza-LOGME-999"},
        headers=as_user(USER_A),
    )
    assert "AIza-LOGME-999" not in caplog.text


# --------------------------- findings ---------------------------


async def test_empty_or_absurd_api_key_rejected(client, env):
    r1 = await client.post(
        "/keys", json={"provider": "gemini", "slot": "primary", "api_key": ""},
        headers=as_user(USER_A),
    )
    r2 = await client.post(
        "/keys", json={"provider": "gemini", "slot": "primary", "api_key": "x" * 2_000_000},
        headers=as_user(USER_A),
    )
    assert r1.status_code == 422 and r2.status_code == 422


async def test_delete_with_malformed_id_is_clean_4xx(client, env):
    r = await client.delete("/keys/not-a-uuid", headers=as_user(USER_A))
    assert r.status_code < 500
