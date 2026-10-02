from pydantic import BaseModel, Field

from app.keys.models import ProviderName


class ScoreRequest(BaseModel):
    resume_id: str
    jd_text: str = Field(min_length=10, max_length=20000)
    provider: ProviderName


class ScoreResponse(BaseModel):
    composite_score: int
    keyword_score: float
    semantic_score: float
    formatting_score: float
    feedback: str
    missing_must_have: list[str]
    missing_nice_to_have: list[str]
