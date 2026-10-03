"""The reviewer's structured answer for a submitted solution.

Field order matters: `trace` comes first so the model reasons about the code
(on concrete inputs) before it commits to a verdict. A "correct" or "mostly
correct" verdict without a real trace is rejected, which makes the gateway's
repair retry ask for one."""

from pydantic import BaseModel, Field, field_validator, model_validator

from app.llm.schemas import TermList

RESULTS = ("correct", "mostly_correct", "incorrect", "incomplete")
APPROACHES = ("same_as_reference", "different_but_valid", "invalid", "incomplete")
CONFIDENCE = ("high", "medium", "low")

_MIN_TRACE_CHARS = 25


def _norm(value) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


class ReviewOut(BaseModel):
    trace: str = Field(min_length=1)
    approach: str
    result: str
    issues: TermList = Field(default_factory=list)
    edge_cases_missed: TermList = Field(default_factory=list)
    candidate_complexity: str = ""
    reference_complexity: str = ""
    confidence: str = "medium"
    summary: str = ""
    interviewer_message: str = Field(min_length=1)

    @field_validator("approach", mode="before")
    @classmethod
    def _approach(cls, value):
        value = _norm(value)
        if value not in APPROACHES:
            raise ValueError(f"approach must be one of {', '.join(APPROACHES)}")
        return value

    @field_validator("result", mode="before")
    @classmethod
    def _result(cls, value):
        value = _norm(value)
        if value not in RESULTS:
            raise ValueError(f"result must be one of {', '.join(RESULTS)}")
        return value

    @field_validator("confidence", mode="before")
    @classmethod
    def _confidence(cls, value):
        value = _norm(value)
        return value if value in CONFIDENCE else "medium"

    @field_validator("trace", "summary", "candidate_complexity", "reference_complexity", "interviewer_message", mode="before")
    @classmethod
    def _text(cls, value):
        return str(value).strip() if value is not None else ""

    @model_validator(mode="after")
    def _correct_needs_evidence(self):
        if self.result in ("correct", "mostly_correct") and len(self.trace) < _MIN_TRACE_CHARS:
            raise ValueError(
                "a correct verdict needs a trace of how the code behaves on specific inputs"
            )
        return self
