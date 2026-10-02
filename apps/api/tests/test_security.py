import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException
from jose import jwt
from jose.backends import ECKey

from app.core import security
from app.core.config import settings


def _claims() -> dict:
    return {
        "sub": "user-1",
        "aud": "authenticated",
        "email": "a@b.com",
        "exp": int(time.time()) + 60,
    }


def _make_ec_keypair():
    private_key = ec.generate_private_key(ec.SECP256R1())
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_jwk = ECKey(private_pem, "ES256").public_key().to_dict()
    return private_pem, public_jwk


@pytest.fixture(autouse=True)
def _clear_cache():
    security._jwks_cache.clear()
    yield
    security._jwks_cache.clear()


@pytest.mark.asyncio
async def test_accepts_es256_token_signed_by_a_key_in_the_jwks(monkeypatch):
    private_pem, public_jwk = _make_ec_keypair()
    public_jwk.update(kid="key-1", alg="ES256")

    async def fake_fetch():
        return {"key-1": public_jwk}

    monkeypatch.setattr(security, "_fetch_jwks", fake_fetch)
    token = jwt.encode(_claims(), private_pem, algorithm="ES256", headers={"kid": "key-1"})

    payload = await security._decode_supabase_jwt(token)

    assert payload["sub"] == "user-1"


@pytest.mark.asyncio
async def test_rejects_es256_token_signed_by_a_different_key(monkeypatch):
    _, trusted_jwk = _make_ec_keypair()
    trusted_jwk.update(kid="key-1", alg="ES256")
    attacker_pem, _ = _make_ec_keypair()

    async def fake_fetch():
        return {"key-1": trusted_jwk}

    monkeypatch.setattr(security, "_fetch_jwks", fake_fetch)
    token = jwt.encode(_claims(), attacker_pem, algorithm="ES256", headers={"kid": "key-1"})

    with pytest.raises(HTTPException) as exc_info:
        await security._decode_supabase_jwt(token)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_rejects_token_with_unknown_kid(monkeypatch):
    private_pem, _ = _make_ec_keypair()

    async def fake_fetch():
        return {}

    monkeypatch.setattr(security, "_fetch_jwks", fake_fetch)
    token = jwt.encode(_claims(), private_pem, algorithm="ES256", headers={"kid": "nope"})

    with pytest.raises(HTTPException) as exc_info:
        await security._decode_supabase_jwt(token)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_still_accepts_legacy_hs256_token(monkeypatch):
    monkeypatch.setattr(settings, "supabase_jwt_secret", "legacy-secret")
    token = jwt.encode(_claims(), "legacy-secret", algorithm="HS256")

    payload = await security._decode_supabase_jwt(token)

    assert payload["sub"] == "user-1"


@pytest.mark.asyncio
async def test_rejects_expired_token(monkeypatch):
    monkeypatch.setattr(settings, "supabase_jwt_secret", "legacy-secret")
    claims = _claims() | {"exp": int(time.time()) - 60}
    token = jwt.encode(claims, "legacy-secret", algorithm="HS256")

    with pytest.raises(HTTPException) as exc_info:
        await security._decode_supabase_jwt(token)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_rejects_garbage_token():
    with pytest.raises(HTTPException) as exc_info:
        await security._decode_supabase_jwt("not.a.jwt")

    assert exc_info.value.status_code == 401
