from typing import Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field

from app.account import service
from app.core.security import AuthenticatedUser, get_current_user

router = APIRouter(prefix="/account", tags=["account"])


class RenameIn(BaseModel):
    full_name: str = Field(max_length=200)


class RenameOut(BaseModel):
    full_name: str


class DeleteIn(BaseModel):
    confirm: Literal["DELETE"]


@router.patch("", response_model=RenameOut)
async def rename(body: RenameIn, user: AuthenticatedUser = Depends(get_current_user)):
    return await service.rename(user.user_id, body.full_name)


@router.post("/delete", status_code=status.HTTP_204_NO_CONTENT)
async def delete(_: DeleteIn, user: AuthenticatedUser = Depends(get_current_user)) -> Response:
    """POST (not DELETE) so the typed confirmation travels in a body."""
    await service.delete(user.user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
