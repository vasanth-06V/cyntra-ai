import logging
import time

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Header, HTTPException, status
from jose import JWTError, jwt

from app.core.config import settings


def _fernet() -> Fernet:
    return Fernet(settings.key_encryption_secret)


def encrypt_key(raw_key: str) -> str:
    return _fernet().encrypt(raw_key.encode()).decode()


def decrypt_key(encrypted_key: str) -> str:
    try:
        return _fernet().decrypt(encrypted_key.encode()).decode()
    except InvalidToken as exc:
        # e.g. the server's encryption secret changed since the key was saved.
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="Your saved API key can't be read -- please re-enter it in Settings -> API Keys.",
        ) from exc


class AuthenticatedUser:
    def __init__(self, user_id: str, email: str | None):
        self.user_id = user_id
        self.email = email


logger = logging.getLogger(__name__)

_jwks_cache: dict[str, dict] = {}
# At most one refetch per interval, so a stream of tokens with made-up key ids
# can't make us hit the JWKS endpoint on every request. (A real key rotation
# is picked up within this window.)
_last_jwks_fetch = 0.0
_JWKS_MIN_REFETCH_SECONDS = 30


async def _fetch_jwks() -> dict[str, dict]:
    url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(url)
        response.raise_for_status()
    return {key["kid"]: key for key in response.json().get("keys", []) if "kid" in key}


async def _signing_key_for(kid: str | None) -> dict | None:
    """Newer Supabase projects sign user tokens with an asymmetric key
    (ES256) published at a JWKS endpoint, not the legacy shared HS256
    secret. Cached by key id; refetched once if a token arrives with a kid
    we haven't seen (i.e. after a key rotation)."""
    if kid is None:
        return None
    global _last_jwks_fetch
    if kid not in _jwks_cache:
        now = time.monotonic()
        if _jwks_cache and now - _last_jwks_fetch < _JWKS_MIN_REFETCH_SECONDS:
            return None
        fetched = await _fetch_jwks()  # raises on an outage; cache is left intact
        _last_jwks_fetch = now
        _jwks_cache.clear()
        _jwks_cache.update(fetched)
    return _jwks_cache.get(kid)


async def _decode_supabase_jwt(token: str) -> dict:
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
    )
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") == "HS256":
            # Legacy shared-secret tokens. With no secret configured this must
            # never verify anything: an empty key would accept tokens anyone
            # can mint.
            if not settings.supabase_jwt_secret:
                raise invalid
            return jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
                options={"require_exp": True},
            )

        key = await _signing_key_for(header.get("kid"))
        if key is None:
            raise invalid
        return jwt.decode(
            token,
            key,
            algorithms=["ES256", "RS256"],
            audience="authenticated",
            options={"require_exp": True},
        )
    except httpx.HTTPError as exc:
        # Our dependency is down -- that's not the user's token being bad.
        logger.error("Could not fetch signing keys: %r", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sign-in verification is temporarily unavailable -- please retry.",
        ) from exc
    except JWTError as exc:
        logger.warning("Rejected bearer token: %r", exc)
        raise invalid from exc


async def get_current_user(authorization: str = Header(default="")) -> AuthenticatedUser:
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )
    token = authorization.removeprefix("Bearer ").strip()
    payload = await _decode_supabase_jwt(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject claim",
        )
    return AuthenticatedUser(user_id=user_id, email=payload.get("email"))
