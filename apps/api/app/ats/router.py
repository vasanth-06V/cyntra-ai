from fastapi import APIRouter, Depends, Query, status

from app.ats import service
from app.ats.models import AtsHistoryDetailOut, AtsHistoryItemOut, ScoreRequest, ScoreResponse
from app.core.ids import UuidStr
from app.core.pagination import Page, page_params
from app.core.security import AuthenticatedUser, get_current_user
from app.core.throttle import limited

router = APIRouter(prefix="/ats", tags=["ats"])


@router.post("/score", response_model=ScoreResponse)
async def score(body: ScoreRequest, user: AuthenticatedUser = Depends(limited("ats.score", 6))):
    return await service.score_resume(
        user.user_id, body.resume_id, body.provider.value, body.jd_text
    )


@router.get("/history", response_model=list[AtsHistoryItemOut])
async def history(
    resume_id: UuidStr | None = Query(default=None),
    user: AuthenticatedUser = Depends(get_current_user),
    page: Page = Depends(page_params),
):
    """Past ATS results (newest first); the last 10 per resume are kept."""
    return await service.list_history(user.user_id, resume_id, page.limit, page.offset)


@router.get("/history/{score_id}", response_model=AtsHistoryDetailOut)
async def history_detail(score_id: UuidStr, user: AuthenticatedUser = Depends(get_current_user)):
    return await service.get_history(user.user_id, score_id)


@router.delete("/history/{score_id}", status_code=status.HTTP_204_NO_CONTENT)
async def history_delete(score_id: UuidStr, user: AuthenticatedUser = Depends(get_current_user)):
    await service.delete_history(user.user_id, score_id)
