from fastapi import APIRouter, Depends

from app.core.security import AuthenticatedUser, get_current_user
from app.db import usage as usage_repo
from app.llm.keystate import quota_day

router = APIRouter(prefix="/usage", tags=["usage"])

_PROVIDERS = ("gemini", "claude", "groq")


async def usage_today(user_id: str) -> list[dict]:
    """Usage for "today" as each provider counts it: Gemini's quota day is
    Pacific, the others' is UTC."""
    today = {provider: quota_day(provider).isoformat() for provider in _PROVIDERS}
    rows = await usage_repo.usage_for_days(user_id, sorted(set(today.values())))
    return [
        {k: v for k, v in row.items() if k != "day"}
        for row in rows
        if row.get("day") == today.get(row["provider"])
    ]


@router.get("")
async def get_usage(user: AuthenticatedUser = Depends(get_current_user)):
    return await usage_today(user.user_id)
