from fastapi import APIRouter, Depends

from app.core.security import AuthenticatedUser, get_current_user
from app.rag import service
from app.rag.models import ProcessResumeResponse

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/resumes/{resume_id}/process", response_model=ProcessResumeResponse)
async def process_resume(
    resume_id: str, user: AuthenticatedUser = Depends(get_current_user)
):
    chunk_count = await service.process_resume(user.user_id, resume_id)
    return ProcessResumeResponse(resume_id=resume_id, chunk_count=chunk_count)
