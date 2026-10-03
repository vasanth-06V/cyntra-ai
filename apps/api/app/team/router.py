from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.ids import UuidStr
from app.core.security import AuthenticatedUser, get_current_user
from app.team import service

router = APIRouter(prefix="/team", tags=["team"])


class TeamUserOut(BaseModel):
    id: str
    email: str | None
    full_name: str | None
    role: Literal["owner", "admin", "user"]
    permissions: list[str]
    created_at: datetime | None = None


class RoleIn(BaseModel):
    role: Literal["admin", "user"]


class RoleOut(BaseModel):
    id: str
    role: str


class PermissionsIn(BaseModel):
    permissions: list[str] = Field(max_length=20)


class PermissionsOut(BaseModel):
    id: str
    permissions: list[str]


@router.get("/users", response_model=list[TeamUserOut])
async def list_users(user: AuthenticatedUser = Depends(get_current_user)):
    return await service.list_users(user.user_id)


@router.patch("/users/{target_id}/role", response_model=RoleOut)
async def set_role(target_id: UuidStr, body: RoleIn, user: AuthenticatedUser = Depends(get_current_user)):
    return await service.set_role(user.user_id, target_id, body.role)


@router.put("/users/{target_id}/permissions", response_model=PermissionsOut)
async def set_permissions(
    target_id: UuidStr, body: PermissionsIn, user: AuthenticatedUser = Depends(get_current_user)
):
    return await service.set_permissions(user.user_id, target_id, body.permissions)
