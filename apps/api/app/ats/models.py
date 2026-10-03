from pydantic import BaseModel, Field

from app.core.ids import UuidStr
from app.keys.models import ProviderName


class ScoreRequest(BaseModel):
    resume_id: UuidStr
    jd_text: str = Field(min_length=10, max_length=20000)
    provider: ProviderName


class CoverageOut(BaseModel):
    """How well the resume backs up one requirement from the job description."""

    term: str
    kind: str  # "must" | "nice"
    covered: bool
    strength: float  # 0..1
    section: str | None = None  # where the best evidence sits (e.g. "experience")
    evidence: str = ""


class ScoreResponse(BaseModel):
    composite_score: int
    keyword_score: float
    semantic_score: float
    formatting_score: float
    feedback: str
    missing_must_have: list[str]
    missing_nice_to_have: list[str]
    coverage: list[CoverageOut] = []
