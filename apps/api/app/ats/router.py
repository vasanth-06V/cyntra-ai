from fastapi import APIRouter, Depends

from app.ats import service
from app.ats.models import ScoreRequest, ScoreResponse
from app.core.security import AuthenticatedUser
from app.core.throttle import limited

router = APIRouter(prefix="/ats", tags=["ats"])


@router.post("/score", response_model=ScoreResponse)
async def score(body: ScoreRequest, user: AuthenticatedUser = Depends(limited("ats.score", 6))):
    return await service.score_resume(
        user.user_id, body.resume_id, body.provider.value, body.jd_text
    )
