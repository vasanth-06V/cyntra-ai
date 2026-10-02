"""LLM gateway behaviour seen through real HTTP endpoints: usage, local rate
limiting, error mapping (including the REAL provider adapters with their SDK
objects mocked), and key-decryption failure."""

import httpx
import pytest
from cryptography.fernet import Fernet

from app.llm.keystate import cooldowns
from app.llm.limiter import limiter
from app.providers import gemini as gemini_mod
from app.providers import groq as groq_mod
from app.providers import registry
from app.providers.base import ProviderAuthError

from .conftest import USER_A, USER_B, as_user, seed_key


async def _chat(client, user=USER_A, provider="gemini", content="hi"):
    conv = (await client.post("/chat/conversations", json={}, headers=as_user(user))).json()["id"]
    return await client.post(
        f"/chat/conversations/{conv}/messages",
        json={"provider": provider, "content": content}, headers=as_user(user),
    )


async def test_usage_endpoint_returns_only_my_totals_and_counts_requests(client, env):
    seed_key(env, USER_A, "gemini", "primary", "a")
    seed_key(env, USER_B, "gemini", "primary", "b")
    await _chat(client, USER_A)
    await _chat(client, USER_A)
    await _chat(client, USER_B)

    mine = (await client.get("/usage", headers=as_user(USER_A))).json()
    theirs = (await client.get("/usage", headers=as_user(USER_B))).json()
    assert [(u["provider"], u["kind"], u["requests"]) for u in mine] == [("gemini", "chat", 2)]
    assert [u["requests"] for u in theirs] == [1]
    assert all("user_id" not in u for u in mine)


async def test_usage_bookkeeping_failure_never_fails_the_request(client, env, monkeypatch):
    seed_key(env, USER_A, "gemini", "primary", "a")

    def boom(name, params):
        raise RuntimeError("db down")

    monkeypatch.setattr(env.db, "run_rpc", boom)
    r = await _chat(client)
    assert r.status_code == 200 and r.text


async def test_local_rate_limit_returns_429_instead_of_hanging(client, env, monkeypatch):
    seed_key(env, USER_A, "gemini", "primary", "a")
    monkeypatch.setattr(limiter, "_limits", {"gemini": 2})
    monkeypatch.setattr(limiter, "_max_wait", 0.0)
    codes = [(await _chat(client)).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
    # another user is not affected by this user's window
    seed_key(env, USER_B, "gemini", "primary", "b")
    assert (await _chat(client, USER_B)).status_code == 200


async def test_provider_auth_error_maps_to_400_key_rejected(client, env):
    seed_key(env, USER_A, "gemini", "primary", "a")
    env.gemini.script = [ProviderAuthError("revoked")]
    r = await _chat(client)
    assert r.status_code == 400 and "rejected" in r.json()["detail"]


async def test_embed_quota_failover_uses_backup_gemini_key(client, env):
    seed_key(env, USER_A, "gemini", "primary", "p")
    seed_key(env, USER_A, "gemini", "backup", "b")
    env.gemini.rate_limited_keys.add("p")
    # question creation (owner) exercises gateway.embed
    env.db.seed("roles", user_id=USER_A, role="owner")
    r = await client.post(
        "/interviews/question-bank",
        json={"type": "hr", "question": "Tell me about yourself"}, headers=as_user(USER_A),
    )
    assert r.status_code == 201
    assert [c.api_key for c in env.gemini.embed_calls] == ["p", "b"]
    assert env.db.rows("notifications", user_id=USER_A)


# --------------- real Gemini adapter, scripted HTTP responses ---------------


def _google_error(status: int, message: str, google_status: str, details=None) -> httpx.Response:
    return httpx.Response(
        status,
        json={"error": {"code": status, "message": message, "status": google_status, "details": details or []}},
    )


@pytest.fixture
def real_gemini(env, monkeypatch):
    """The real adapter and the real wire parsing; only the network is scripted."""

    class Script:
        response: httpx.Response = httpx.Response(200, json={})

    def handler(request: httpx.Request) -> httpx.Response:
        return Script.response

    adapter = gemini_mod.GeminiAdapter(transport=httpx.MockTransport(handler))
    monkeypatch.setitem(registry._ADAPTERS, "gemini", adapter)
    return Script


async def test_real_gemini_adapter_maps_rate_limit_overload_and_key_errors(client, env, real_gemini):
    seed_key(env, USER_A, "gemini", "primary", "a")
    real_gemini.response = _google_error(429, "Quota exceeded", "RESOURCE_EXHAUSTED")
    assert (await _chat(client)).status_code == 429
    cooldowns.clear()  # the 429 above (correctly) put the key on cooldown
    real_gemini.response = _google_error(503, "The model is overloaded", "UNAVAILABLE")
    assert (await _chat(client)).status_code == 503
    real_gemini.response = _google_error(403, "Permission denied", "PERMISSION_DENIED")
    r = await _chat(client)
    assert r.status_code == 400 and r.json()["error"]["code"] == "key_rejected"


async def test_real_gemini_bad_api_key_is_a_key_error_not_a_500(client, env, real_gemini):
    seed_key(env, USER_A, "gemini", "primary", "a")
    real_gemini.response = _google_error(400, "API key not valid. Please pass a valid API key.", "INVALID_ARGUMENT")
    r = await _chat(client)
    assert r.status_code == 400 and r.json()["error"]["code"] == "key_rejected"


async def test_real_gemini_bad_request_is_not_blamed_on_the_users_key(client, env, real_gemini):
    seed_key(env, USER_A, "gemini", "primary", "a")
    real_gemini.response = _google_error(400, "The input token count exceeds the maximum", "INVALID_ARGUMENT")
    r = await _chat(client)
    assert r.status_code == 502 and r.json()["error"]["code"] == "provider_bad_request"


async def test_real_gemini_retired_model_is_a_clear_config_error_and_not_retried(client, env, real_gemini):
    seed_key(env, USER_A, "gemini", "primary", "a")
    real_gemini.response = _google_error(404, "models/gemini-x is not found", "NOT_FOUND")
    r = await _chat(client)
    assert r.status_code == 503 and r.json()["error"]["code"] == "provider_misconfigured"


async def test_real_groq_model_not_found_is_not_a_500(client, env, monkeypatch):
    import groq

    seed_key(env, USER_A, "groq", "primary", "g")
    monkeypatch.setitem(registry._ADAPTERS, "groq", groq_mod.GroqAdapter())

    class _Completions:
        async def create(self, *a, **kw):
            req = httpx.Request("POST", "http://x")
            raise groq.NotFoundError("model not found", response=httpx.Response(404, request=req), body=None)

    class _Client:
        def __init__(self, *a, **kw):
            self.chat = type("C", (), {"completions": _Completions()})()

    monkeypatch.setattr(groq_mod, "AsyncGroq", _Client)
    assert (await _chat(client, provider="groq")).status_code != 500


async def test_undecryptable_key_is_not_a_500(client, env):
    other = Fernet(Fernet.generate_key()).encrypt(b"old-key").decode()
    env.db.seed("provider_keys", user_id=USER_A, provider="gemini", slot="primary",
                encrypted_key=other, is_valid=True)
    assert (await _chat(client)).status_code != 500
