from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from app.coding import service
from app.core.ids import UuidStr
from app.core.security import AuthenticatedUser, get_current_user
from app.core.throttle import limited

router = APIRouter(prefix="/interviews", tags=["coding"])


class SubmitCodeRequest(BaseModel):
    language: str = Field(min_length=1, max_length=30)
    code: str = Field(min_length=1, max_length=service.MAX_CODE_CHARS)


class SubmissionStartedOut(BaseModel):
    job_id: str
    submission_id: str


class ProblemOut(BaseModel):
    enabled: bool
    active: bool
    phase: str | None = None
    problem_number: int | None = None
    total_problems: int | None = None
    question: str | None = None
    submission: dict | None = None
    review_job_id: str | None = None


@router.get("/{interview_id}/problem", response_model=ProblemOut)
async def get_problem(interview_id: UuidStr, user: AuthenticatedUser = Depends(get_current_user)):
    return await service.get_problem(user.user_id, interview_id)


@router.post(
    "/{interview_id}/submissions",
    response_model=SubmissionStartedOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_code(
    interview_id: UuidStr,
    body: SubmitCodeRequest,
    user: AuthenticatedUser = Depends(limited("code.submit", 6)),
):
    """One submission per problem. Returns a job at once; poll GET /jobs/{job_id}
    and read the interviewer's reaction from its result."""
    return await service.begin_review(user.user_id, interview_id, body.language, body.code)
