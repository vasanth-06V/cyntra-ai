from fastapi import APIRouter, Depends, status

from app.core.ids import UuidStr
from app.core.security import AuthenticatedUser, get_current_user
from app.core.throttle import limited
from app.keys import service
from app.keys.models import ProviderKeyOut, SubmitKeyRequest

router = APIRouter(prefix="/keys", tags=["keys"])


@router.post("", response_model=ProviderKeyOut, status_code=status.HTTP_201_CREATED)
async def submit_key(
    body: SubmitKeyRequest, user: AuthenticatedUser = Depends(limited("keys.submit", 10))
):
    row = await service.submit_key(
        user_id=user.user_id,
        provider=body.provider.value,
        slot=body.slot.value,
        api_key=body.api_key,
    )
    return row


@router.get("", response_model=list[ProviderKeyOut])
async def list_keys(user: AuthenticatedUser = Depends(get_current_user)):
    return await service.list_keys(user.user_id)


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_key(key_id: UuidStr, user: AuthenticatedUser = Depends(get_current_user)):
    await service.delete_key(user.user_id, key_id)
