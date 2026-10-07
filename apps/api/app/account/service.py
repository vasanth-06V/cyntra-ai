"""The signed-in user's own account: rename and delete."""

import logging

from fastapi import status

from app.core.errors import AppError
from app.db import account as account_repo
from app.db import questions as questions_repo

logger = logging.getLogger(__name__)

MAX_NAME_LENGTH = 80


async def rename(user_id: str, full_name: str) -> dict:
    name = " ".join(full_name.split())
    if not name or len(name) > MAX_NAME_LENGTH:
        raise AppError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "validation_failed",
            f"The name must be 1-{MAX_NAME_LENGTH} characters.",
        )
    if not await account_repo.set_full_name(user_id, name):
        raise AppError(status.HTTP_404_NOT_FOUND, "not_found", "Account not found.")
    return {"full_name": name}


async def delete(user_id: str) -> None:
    """Permanently deletes the account and everything it owns. The Owner can't
    be deleted: the platform would be left without one."""
    if await questions_repo.get_role(user_id) == "owner":
        raise AppError(
            status.HTTP_409_CONFLICT,
            "owner_cannot_delete",
            "The Owner account can't be deleted. Contact the platform operator.",
        )
    await account_repo.delete_auth_user(user_id)
    logger.info("account: user %s deleted their account", user_id)
