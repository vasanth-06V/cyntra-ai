"""Auth: every route needs a user, and the real JWT dependency behaves.

The first block uses the real `get_current_user` (override removed). The
JWKS key pair is generated locally; no network is used.
"""

import time

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from jose import jwk, jwt

from app.core import security
from app.core.config import settings
from app.core.security import get_current_user
from app.main import app

from .conftest import USER_A

SECRET = "unit-test-secret-not-a-real-one-0123456789"

# (method, path) for every public endpoint.
PROTECTED = [
    ("GET", "/health/authenticated"),
    ("GET", "/keys"),
    ("POST", "/keys"),
    ("DELETE", "/keys/11111111-1111-1111-1111-111111111111"),
    ("GET", "/usage"),
    ("GET", "/chat/conversations"),
    ("POST", "/chat/conversations"),
    ("GET", "/chat/conversations/11111111-1111-1111-1111-111111111111/messages"),
    ("POST", "/chat/conversations/11111111-1111-1111-1111-111111111111/messages"),
    ("POST", "/rag/resumes/11111111-1111-1111-1111-111111111111/process"),
    ("POST", "/ats/score"),
    ("POST", "/interviews"),
    ("GET", "/interviews"),
    ("GET", "/interviews/question-bank"),
    ("POST", "/interviews/question-bank"),
    ("PATCH", "/interviews/question-bank/11111111-1111-1111-1111-111111111111"),
    ("DELETE", "/interviews/question-bank/11111111-1111-1111-1111-111111111111"),
    ("GET", "/interviews/11111111-1111-1111-1111-111111111111"),
    ("GET", "/interviews/11111111-1111-1111-1111-111111111111/transcript"),
    ("POST", "/interviews/11111111-1111-1111-1111-111111111111/turns"),
    ("POST", "/interviews/11111111-1111-1111-1111-111111111111/complete"),
]


@pytest.fixture
async def raw_client(monkeypatch):
    """No dependency override: the real JWT verification runs."""
    app.dependency_overrides.pop(get_current_user, None)
    monkeypatch.setattr(settings, "supabase_jwt_secret", SECRET)
    monkeypatch.setattr(settings, "supabase_url", "https://example.invalid")
    security._jwks_cache.clear()
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    security._jwks_cache.clear()


def _hs256(claims=None, secret=SECRET):
    claims = {"sub": USER_A, "aud": "authenticated", "exp": int(time.time()) + 600,
              "email": "a@example.com", **(claims or {})}
    return jwt.encode(claims, secret, algorithm="HS256")


@pytest.mark.parametrize("method,path", PROTECTED)
async def test_every_endpoint_rejects_missing_and_garbage_tokens(raw_client, method, path):
    r = await raw_client.request(method, path, json={})
    assert r.status_code == 401, (method, path, r.status_code)
    r = await raw_client.request(method, path, json={}, headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401, (method, path, r.status_code)


async def test_health_is_public(raw_client):
    assert (await raw_client.get("/health")).status_code == 200


async def test_valid_hs256_token_accepted(raw_client):
    r = await raw_client.get("/health/authenticated", headers={"Authorization": f"Bearer {_hs256()}"})
    assert r.status_code == 200 and r.json()["user_id"] == USER_A


async def test_expired_wrong_audience_wrong_secret_and_no_subject_rejected(raw_client):
    cases = [
        _hs256({"exp": int(time.time()) - 10}),
        _hs256({"aud": "anon"}),
        _hs256(secret="some-other-secret-value-xxxxxxxxxxxxxxxx"),
        jwt.encode({"aud": "authenticated", "exp": int(time.time()) + 60}, SECRET, algorithm="HS256"),
    ]
    for token in cases:
        r = await raw_client.get("/health/authenticated", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401


async def test_alg_none_token_rejected(raw_client):
    import base64, json
    def b64(d): return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    token = f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64({'sub': USER_A, 'aud': 'authenticated'})}."
    r = await raw_client.get("/health/authenticated", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def _es256_material(kid="kid-1"):
    key = ec.generate_private_key(ec.SECP256R1())
    private_pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    public_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()
    public_jwk = jwk.construct(public_pem, "ES256").to_dict()
    public_jwk["kid"] = kid
    return private_pem, public_jwk


async def test_es256_token_verified_against_jwks_and_cache_is_used(raw_client, monkeypatch):
    private_pem, public_jwk = _es256_material()
    fetches = []

    async def fake_fetch():
        fetches.append(1)
        return {public_jwk["kid"]: public_jwk}

    monkeypatch.setattr(security, "_fetch_jwks", fake_fetch)
    token = jwt.encode(
        {"sub": USER_A, "aud": "authenticated", "exp": int(time.time()) + 600},
        private_pem, algorithm="ES256", headers={"kid": "kid-1"},
    )
    for _ in range(3):
        r = await raw_client.get("/health/authenticated", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
    assert len(fetches) == 1


async def test_es256_token_signed_by_a_different_key_rejected(raw_client, monkeypatch):
    _, public_jwk = _es256_material()
    attacker_pem, _ = _es256_material()

    async def fake_fetch():
        return {"kid-1": public_jwk}

    monkeypatch.setattr(security, "_fetch_jwks", fake_fetch)
    token = jwt.encode(
        {"sub": USER_A, "aud": "authenticated", "exp": int(time.time()) + 600},
        attacker_pem, algorithm="ES256", headers={"kid": "kid-1"},
    )
    r = await raw_client.get("/health/authenticated", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


# --------------------------- findings ---------------------------


async def test_forged_token_accepted_when_jwt_secret_is_unset(raw_client, monkeypatch):
    """CONFIRMED (HIGH): with SUPABASE_JWT_SECRET empty -- exactly what the
    working-directory .env bug produced in the first live run -- anyone can
    mint an HS256 token for any user id and the API accepts it. This test
    pins the fix: an unset secret must never verify anything."""
    monkeypatch.setattr(settings, "supabase_jwt_secret", "")
    forged = jwt.encode({"sub": "any-victim-id", "aud": "authenticated"}, "", algorithm="HS256")
    r = await raw_client.get("/health/authenticated", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401


async def test_unknown_kid_does_not_trigger_a_jwks_fetch_per_request(raw_client, monkeypatch):
    _, public_jwk = _es256_material()
    fetches = []

    async def fake_fetch():
        fetches.append(1)
        return {"kid-1": public_jwk}

    monkeypatch.setattr(security, "_fetch_jwks", fake_fetch)
    attacker_pem, _ = _es256_material()
    for i in range(5):
        token = jwt.encode(
            {"sub": USER_A, "aud": "authenticated", "exp": int(time.time()) + 60},
            attacker_pem, algorithm="ES256", headers={"kid": f"random-{i}"},
        )
        await raw_client.get("/health/authenticated", headers={"Authorization": f"Bearer {token}"})
    assert len(fetches) <= 1


async def test_jwks_outage_is_not_reported_as_invalid_token(raw_client, monkeypatch):
    private_pem, _ = _es256_material()

    async def boom():
        raise httpx.ConnectError("jwks down")

    monkeypatch.setattr(security, "_fetch_jwks", boom)
    token = jwt.encode(
        {"sub": USER_A, "aud": "authenticated", "exp": int(time.time()) + 60},
        private_pem, algorithm="ES256", headers={"kid": "kid-1"},
    )
    r = await raw_client.get("/health/authenticated", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 503


async def test_token_without_expiry_rejected(raw_client):
    token = jwt.encode({"sub": USER_A, "aud": "authenticated"}, SECRET, algorithm="HS256")
    r = await raw_client.get("/health/authenticated", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
