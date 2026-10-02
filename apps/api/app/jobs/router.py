from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.errors import AppError
from app.core.ids import UuidStr
from app.core.security import AuthenticatedUser, get_current_user
from app.db import jobs as jobs_repo

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobOut(BaseModel):
    id: str
    kind: str
    status: str  # queued | running | succeeded | failed
    progress: str | None = None
    result: dict | None = None
    error: dict | None = None  # {code, message, status}
    subject_id: str | None = None
    created_at: datetime


@router.get("/{job_id}", response_model=JobOut)
async def get_job(job_id: UuidStr, user: AuthenticatedUser = Depends(get_current_user)):
    job = await jobs_repo.get_owned_job(user.user_id, job_id)
    if not job:
        raise AppError(404, "not_found", "Job not found")
    return job
