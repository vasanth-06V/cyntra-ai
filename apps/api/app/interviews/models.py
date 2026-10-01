from datetime import datetime
from enum import Enum

from pydantic import BaseModel


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
    jd_text: str


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
    content: str


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
    question: str
    test_cases: list | None = None
    tags: list[str] | None = None


class QuestionUpdateIn(BaseModel):
    question: str | None = None
    test_cases: list | None = None
    tags: list[str] | None = None


class QuestionOut(BaseModel):
    id: str
    type: str
    question: str
    test_cases: list | None
    tags: list[str] | None
    created_by: str | None
    created_at: datetime
