import httpx
from cryptography.fernet import Fernet
from fastapi import Header, HTTPException, status
from jose import JWTError, jwt

from app.core.config import settings


def _fernet() -> Fernet:
    return Fernet(settings.key_encryption_secret)


def encrypt_key(raw_key: str) -> str:
    return _fernet().encrypt(raw_key.encode()).decode()


def decrypt_key(encrypted_key: str) -> str:
    return _fernet().decrypt(encrypted_key.encode()).decode()


class AuthenticatedUser:
    def __init__(self, user_id: str, email: str | None):
        self.user_id = user_id
        self.email = email


_jwks_cache: dict[str, dict] = {}


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
    if kid not in _jwks_cache:
        _jwks_cache.clear()
        _jwks_cache.update(await _fetch_jwks())
    return _jwks_cache.get(kid)


async def _decode_supabase_jwt(token: str) -> dict:
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
    )
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") == "HS256":
            # Legacy shared-secret tokens.
            return jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
            )

        key = await _signing_key_for(header.get("kid"))
        if key is None:
            raise invalid
        return jwt.decode(
            token, key, algorithms=["ES256", "RS256"], audience="authenticated"
        )
    except (JWTError, httpx.HTTPError) as exc:
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
