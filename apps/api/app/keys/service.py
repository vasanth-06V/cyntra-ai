from datetime import UTC, datetime

from fastapi import status

from app.core.errors import AppError
from app.core.security import encrypt_key
from app.db import keys as keys_repo
from app.providers.base import ProviderRateLimitError, ProviderUnavailableError
from app.providers.registry import get_adapter


async def submit_key(user_id: str, provider: str, slot: str, api_key: str) -> dict:
    """Validates first and only stores a key that passed, so re-saving can
    never replace a working key with a bad or unconfirmed one (which would
    bounce the user back to onboarding)."""
    adapter = get_adapter(provider)
    try:
        is_valid = await adapter.validate(api_key)
    except ProviderRateLimitError as exc:
        raise AppError(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "provider_rate_limited",
            f"{provider.capitalize()} is rate-limiting right now, so the key couldn't be checked. Nothing was saved -- try again in a minute.",
        ) from exc
    except ProviderUnavailableError as exc:
        raise AppError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "provider_overloaded",
            f"{provider.capitalize()} is temporarily unavailable, so the key couldn't be checked. Nothing was saved -- try again shortly.",
        ) from exc

    if not is_valid:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            "key_rejected",
            f"{provider.capitalize()} rejected this key -- double-check it's correct. Nothing was saved.",
        )

    return await keys_repo.upsert_key(
        user_id, provider, slot, encrypt_key(api_key), datetime.now(UTC).isoformat()
    )


async def list_keys(user_id: str) -> list[dict]:
    return await keys_repo.list_keys(user_id)


async def delete_key(user_id: str, key_id: str) -> None:
    await keys_repo.delete_key(user_id, key_id)
