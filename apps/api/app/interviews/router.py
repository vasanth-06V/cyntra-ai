from fastapi import APIRouter, Depends, status

from app.core.ids import UuidStr
from app.core.pagination import Page, large_page_params, page_params
from app.core.security import AuthenticatedUser, get_current_user
from app.core.throttle import limited
from app.interviews import question_bank, service
from app.interviews.models import (
    InterviewType,
    InterviewOut,
    QuestionIn,
    QuestionOut,
    QuestionUpdateIn,
    SetupStartedOut,
    StartInterviewRequest,
    SubmitTurnRequest,
    TranscriptEntryOut,
    TurnResponse,
)

router = APIRouter(prefix="/interviews", tags=["interviews"])


# --- Question bank admin CRUD (Owner, or Admin with permission) ---
# Registered before the /{interview_id} routes below: FastAPI/Starlette
# matches routes in registration order, not by specificity, so a literal
# path like /interviews/question-bank would otherwise be swallowed by
# GET /{interview_id} with interview_id="question-bank".


@router.post(
    "/question-bank", response_model=QuestionOut, status_code=status.HTTP_201_CREATED
)
async def create_question(body: QuestionIn, user: AuthenticatedUser = Depends(get_current_user)):
    return await question_bank.create_question(
        user.user_id, body.type.value, body.question, body.test_cases, body.tags,
        body.difficulty, body.topic,
    )


@router.get("/question-bank", response_model=list[QuestionOut])
async def list_questions(
    type: InterviewType | None = None,
    user: AuthenticatedUser = Depends(get_current_user),
    page: Page = Depends(large_page_params),
):
    return await question_bank.list_questions(
        user.user_id, type.value if type else None, page.limit, page.offset
    )


@router.patch("/question-bank/{question_id}", response_model=QuestionOut)
async def update_question(
    question_id: UuidStr,
    body: QuestionUpdateIn,
    user: AuthenticatedUser = Depends(get_current_user),
):
    return await question_bank.update_question(
        user.user_id, question_id, body.question, body.test_cases, body.tags,
        body.difficulty, body.topic,
    )


@router.delete("/question-bank/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question(
    question_id: UuidStr, user: AuthenticatedUser = Depends(get_current_user)
):
    await question_bank.delete_question(user.user_id, question_id)


# --- Interview lifecycle ---


@router.post("", response_model=SetupStartedOut, status_code=status.HTTP_202_ACCEPTED)
async def start_interview(
    body: StartInterviewRequest, user: AuthenticatedUser = Depends(limited("interviews.start", 4))
):
    """Starts the setup as a job and returns at once; poll GET /jobs/{job_id}
    (status, progress, error) and open the interview when it succeeds."""
    return await service.begin_setup(
        user.user_id, body.type.value, body.provider.value, body.resume_id, body.jd_text
    )


@router.get("", response_model=list[InterviewOut])
async def list_interviews(
    user: AuthenticatedUser = Depends(get_current_user), page: Page = Depends(page_params)
):
    return await service.list_interviews(user.user_id, page.limit, page.offset)


@router.get("/{interview_id}", response_model=InterviewOut)
async def get_interview(interview_id: UuidStr, user: AuthenticatedUser = Depends(get_current_user)):
    return await service.get_interview(user.user_id, interview_id)


@router.get("/{interview_id}/transcript", response_model=list[TranscriptEntryOut])
async def get_transcript(interview_id: UuidStr, user: AuthenticatedUser = Depends(get_current_user)):
    return await service.get_transcript(user.user_id, interview_id)


@router.post("/{interview_id}/turns", response_model=TurnResponse)
async def submit_turn(
    interview_id: UuidStr,
    body: SubmitTurnRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    return await service.submit_turn(user.user_id, interview_id, body.content)


@router.post("/{interview_id}/complete", response_model=InterviewOut)
async def complete_interview(
    interview_id: UuidStr, user: AuthenticatedUser = Depends(get_current_user)
):
    return await service.complete_interview(user.user_id, interview_id)
