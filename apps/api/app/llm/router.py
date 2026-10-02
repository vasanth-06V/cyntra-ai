import asyncio
from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from app.core.db import get_supabase
from app.core.security import AuthenticatedUser, get_current_user

router = APIRouter(prefix="/usage", tags=["usage"])


async def usage_today(user_id: str) -> list[dict]:
    supabase = get_supabase()
    today = datetime.now(UTC).date().isoformat()

    def _query():
        return (
            supabase.table("llm_usage")
            .select("provider, kind, requests, input_tokens, output_tokens")
            .eq("user_id", user_id)
            .eq("day", today)
            .execute()
        )

    result = await asyncio.to_thread(_query)
    return result.data or []


@router.get("")
async def get_usage(user: AuthenticatedUser = Depends(get_current_user)):
    return await usage_today(user.user_id)
