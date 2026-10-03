"""Team management -- the Owner promotes users to Admin and grants permissions.

Only the Owner may use any of this; the checks live here (the service role
bypasses row-level security), and every change is logged."""

import asyncio
import logging

from fastapi import status

from app.core.errors import AppError
from app.db import questions as questions_repo
from app.db import team as team_repo

logger = logging.getLogger(__name__)

# The permissions an Admin can be granted (the keys the rest of the app checks).
PERMISSIONS = ("manage_question_bank",)
ASSIGNABLE_ROLES = ("admin", "user")


async def _require_owner(user_id: str) -> None:
    if await questions_repo.get_role(user_id) != "owner":
        raise AppError(status.HTTP_403_FORBIDDEN, "forbidden", "Only the Owner can manage the team.")


async def _target(owner_id: str, target_id: str) -> str:
    """The target's current role, or a clear refusal."""
    if target_id == owner_id:
        raise AppError(status.HTTP_409_CONFLICT, "cannot_change_owner", "The Owner's own role can't be changed.")
    if not await team_repo.profile_exists(target_id):
        raise AppError(status.HTTP_404_NOT_FOUND, "not_found", "User not found.")
    role = await questions_repo.get_role(target_id) or "user"
    if role == "owner":
        raise AppError(status.HTTP_409_CONFLICT, "cannot_change_owner", "An Owner's role can't be changed.")
    return role


async def list_users(owner_id: str) -> list[dict]:
    await _require_owner(owner_id)
    accounts, profiles, roles, perms = await asyncio.gather(
        team_repo.list_auth_users(),
        team_repo.list_profiles(),
        team_repo.list_roles(),
        team_repo.list_permissions(),
    )
    names = {p["id"]: p for p in profiles}
    role_of = {r["user_id"]: r["role"] for r in roles}
    perms_of: dict[str, list[str]] = {}
    for p in perms:
        perms_of.setdefault(p["admin_id"], []).append(p["permission_key"])

    users = []
    for account in accounts:
        uid = account["id"]
        profile = names.get(uid, {})
        users.append(
            {
                "id": uid,
                "email": account["email"],
                "full_name": profile.get("full_name"),
                "role": role_of.get(uid, "user"),
                "permissions": sorted(perms_of.get(uid, [])),
                "created_at": profile.get("created_at"),
            }
        )
    order = {"owner": 0, "admin": 1, "user": 2}
    return sorted(users, key=lambda u: (order.get(u["role"], 3), (u["email"] or "").lower()))


async def set_role(owner_id: str, target_id: str, role: str) -> dict:
    await _require_owner(owner_id)
    if role not in ASSIGNABLE_ROLES:
        raise AppError(status.HTTP_422_UNPROCESSABLE_ENTITY, "validation_failed", "Role must be admin or user.")
    previous = await _target(owner_id, target_id)
    await team_repo.set_role(target_id, role)
    if role == "user":
        # A plain user holds no permissions: demoting clears them.
        await team_repo.replace_permissions(target_id, [], owner_id)
    logger.info("team: owner %s changed role of %s from %s to %s", owner_id, target_id, previous, role)
    return {"id": target_id, "role": role}


async def set_permissions(owner_id: str, target_id: str, permissions: list[str]) -> dict:
    await _require_owner(owner_id)
    unknown = sorted(set(permissions) - set(PERMISSIONS))
    if unknown:
        raise AppError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "validation_failed",
            f"Unknown permission: {', '.join(unknown)}.",
        )
    role = await _target(owner_id, target_id)
    if role != "admin":
        raise AppError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "not_an_admin",
            "Make this user an Admin before granting permissions.",
        )
    keys = sorted(set(permissions))
    await team_repo.replace_permissions(target_id, keys, owner_id)
    logger.info("team: owner %s set permissions of %s to %s", owner_id, target_id, keys)
    return {"id": target_id, "permissions": keys}
