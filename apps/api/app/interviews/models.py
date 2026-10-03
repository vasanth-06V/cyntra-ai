from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class InterviewProviderName(str, Enum):
    GEMINI = "gemini"
    GROQ = "groq"


class InterviewType(str, Enum):
    CODING = "coding"
    BEHAVIORAL = "behavioral"
    HR = "hr"
    ML_AI = "ml_ai"
    WEBD = "webd"
    SDE = "sde"
    SYSTEM_DESIGN = "system_design"
    CASE_STUDY = "case_study"


class StartInterviewRequest(BaseModel):
    type: InterviewType
    provider: InterviewProviderName
    resume_id: str
    jd_text: str = Field(min_length=10, max_length=20000)


class SetupStartedOut(BaseModel):
    job_id: str
    interview_id: str


class InterviewOut(BaseModel):
    id: str
    type: str
    status: str
    phase: str | None
    provider: str
    resume_id: str
    started_at: datetime | None
    ends_at: datetime | None
    created_at: datetime


class SubmitTurnRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class TurnResponse(BaseModel):
    message: str
    phase: str
    minutes_remaining: float
    is_final_phase: bool


class TranscriptEntryOut(BaseModel):
    id: str
    turn_index: int
    speaker: str
    text: str
    created_at: datetime


class QuestionIn(BaseModel):
    type: InterviewType
    question: str = Field(min_length=1, max_length=4000)
    # Coding-round questions carry a reference solution the reviewer compares
    # candidates against (required for those types; never sent to candidates).
    solution_code: str | None = Field(default=None, max_length=8000)
    solution_language: str | None = Field(default=None, max_length=30)
    test_cases: list | None = None
    tags: list[str] | None = None
    difficulty: int | None = Field(default=None, ge=1, le=5)
    topic: str | None = Field(default=None, max_length=60)


class QuestionUpdateIn(BaseModel):
    question: str | None = Field(default=None, min_length=1, max_length=4000)
    solution_code: str | None = Field(default=None, max_length=8000)
    solution_language: str | None = Field(default=None, max_length=30)
    test_cases: list | None = None
    tags: list[str] | None = None
    difficulty: int | None = Field(default=None, ge=1, le=5)
    topic: str | None = Field(default=None, max_length=60)


class QuestionOut(BaseModel):
    id: str
    type: str
    question: str
    solution_code: str | None = None
    solution_language: str | None = None
    test_cases: list | None
    tags: list[str] | None
    difficulty: int | None = None
    topic: str | None = None
    created_by: str | None
    created_at: datetime
