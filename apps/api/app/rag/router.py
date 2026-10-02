from fastapi import APIRouter, Depends

from app.core.ids import UuidStr
from app.core.security import AuthenticatedUser
from app.core.throttle import limited
from app.rag import service
from app.rag.models import ProcessResumeResponse

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/resumes/{resume_id}/process", response_model=ProcessResumeResponse)
async def process_resume(
    resume_id: UuidStr, user: AuthenticatedUser = Depends(limited("rag.process", 6))
):
    chunk_count = await service.process_resume(user.user_id, resume_id)
    return ProcessResumeResponse(resume_id=resume_id, chunk_count=chunk_count)
