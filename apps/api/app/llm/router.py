from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from app.core.security import AuthenticatedUser, get_current_user
from app.db import usage as usage_repo

router = APIRouter(prefix="/usage", tags=["usage"])


async def usage_today(user_id: str) -> list[dict]:
    today = datetime.now(UTC).date().isoformat()
    return await usage_repo.usage_for_day(user_id, today)


@router.get("")
async def get_usage(user: AuthenticatedUser = Depends(get_current_user)):
    return await usage_today(user.user_id)
