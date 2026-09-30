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


def _decode_supabase_jwt(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc


async def get_current_user(authorization: str = Header(default="")) -> AuthenticatedUser:
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )
    token = authorization.removeprefix("Bearer ").strip()
    payload = _decode_supabase_jwt(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject claim",
        )
    return AuthenticatedUser(user_id=user_id, email=payload.get("email"))
