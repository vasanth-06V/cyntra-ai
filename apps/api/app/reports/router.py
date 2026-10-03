from datetime import datetime

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from app.core.ids import UuidStr
from app.core.pagination import Page, page_params
from app.core.security import AuthenticatedUser, get_current_user
from app.core.throttle import limited
from app.reports import service

router = APIRouter(tags=["reports"])


class ReportStartedOut(BaseModel):
    ready: bool
    job_id: str | None = None


class ReportSummaryOut(BaseModel):
    interview_id: str
    interview_type: str
    overall_score: int
    created_at: datetime
    expires_at: datetime


class ReportOut(ReportSummaryOut):
    report: dict


@router.post(
    "/interviews/{interview_id}/report",
    response_model=ReportStartedOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_report(
    interview_id: UuidStr, user: AuthenticatedUser = Depends(limited("reports.generate", 3))
):
    """Starts the report job (or says it is already ready). Poll GET /jobs/{job_id}."""
    return await service.begin_report(user.user_id, interview_id)


@router.get("/reports", response_model=list[ReportSummaryOut])
async def list_reports(
    user: AuthenticatedUser = Depends(get_current_user), page: Page = Depends(page_params)
):
    return await service.list_reports(user.user_id, page.limit, page.offset)


@router.get("/reports/{interview_id}", response_model=ReportOut)
async def get_report(interview_id: UuidStr, user: AuthenticatedUser = Depends(get_current_user)):
    return await service.get_report(user.user_id, interview_id)


@router.delete("/reports/{interview_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(interview_id: UuidStr, user: AuthenticatedUser = Depends(get_current_user)):
    await service.delete_report(user.user_id, interview_id)
