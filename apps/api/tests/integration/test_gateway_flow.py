"""LLM gateway behaviour seen through real HTTP endpoints: usage, local rate
limiting, error mapping (including the REAL provider adapters with their SDK
objects mocked), and key-decryption failure."""

import httpx
import pytest
from cryptography.fernet import Fernet
from google.api_core import exceptions as gexc

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


# --------------- real adapters, mocked SDK objects ---------------


class _ExplodingModel:
    def __init__(self, exc):
        self.exc = exc

    async def generate_content_async(self, *a, **kw):
        raise self.exc


@pytest.fixture
def real_gemini(env, monkeypatch):
    adapter = gemini_mod.GeminiAdapter()
    monkeypatch.setitem(registry._ADAPTERS, "gemini", adapter)
    return adapter


def _gemini_raises(monkeypatch, exc):
    monkeypatch.setattr(gemini_mod, "_build_model", lambda *a, **kw: _ExplodingModel(exc))


async def test_real_gemini_adapter_maps_rate_limit_and_overload(client, env, real_gemini, monkeypatch):
    seed_key(env, USER_A, "gemini", "primary", "a")
    _gemini_raises(monkeypatch, gexc.ResourceExhausted("quota"))
    assert (await _chat(client)).status_code == 429
    _gemini_raises(monkeypatch, gexc.ServiceUnavailable("high demand"))
    assert (await _chat(client)).status_code == 503
    _gemini_raises(monkeypatch, gexc.PermissionDenied("denied"))
    assert (await _chat(client)).status_code == 400


async def test_real_gemini_invalid_argument_key_error_is_not_a_500(client, env, real_gemini, monkeypatch):
    seed_key(env, USER_A, "gemini", "primary", "a")
    _gemini_raises(monkeypatch, gexc.InvalidArgument("API key not valid. Please pass a valid API key."))
    assert (await _chat(client)).status_code != 500


async def test_real_gemini_model_not_found_is_not_a_500(client, env, real_gemini, monkeypatch):
    seed_key(env, USER_A, "gemini", "primary", "a")
    _gemini_raises(monkeypatch, gexc.NotFound("models/gemini-x is not found"))
    assert (await _chat(client)).status_code != 500


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
