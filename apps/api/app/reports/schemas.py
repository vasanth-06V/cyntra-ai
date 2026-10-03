"""The model's structured answer for an interview report. Models are sloppy
(a string where an object was asked for, scores as "4/5" or 7), so each field
coerces what it safely can; the overall score is NOT part of it -- we compute
that ourselves."""

import re
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, field_validator, model_validator

from app.llm.untrusted import neutralize_tags, strip_controls

DIMENSIONS = ("communication", "structure", "technical_depth", "role_relevance", "coding_quality")
_MAX_TEXT = 260
_MAX_QUOTE = 240


def _text(value, limit: int = _MAX_TEXT) -> str:
    if value is None:
        return ""
    return neutralize_tags(strip_controls(str(value))).strip()[:limit]


class DimensionOut(BaseModel):
    score: int | None = None
    reason: str = ""
    quote: str | None = None

    @field_validator("score", mode="before")
    @classmethod
    def _score(cls, value):
        """1..5, or None when the model says there is not enough evidence."""
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, str):
            match = re.search(r"\d+(?:\.\d+)?", value)
            if not match:
                return None
            value = float(match.group())
        if isinstance(value, (int, float)):
            return min(5, max(1, round(value)))
        return None

    @field_validator("reason", mode="before")
    @classmethod
    def _reason(cls, value):
        return _text(value)

    @field_validator("quote", mode="before")
    @classmethod
    def _quote(cls, value):
        text = _text(value, _MAX_QUOTE)
        return text or None


class ItemOut(BaseModel):
    point: str = Field(min_length=1)
    quote: str | None = None

    @field_validator("point", mode="before")
    @classmethod
    def _point(cls, value):
        return _text(value)

    @field_validator("quote", mode="before")
    @classmethod
    def _quote(cls, value):
        text = _text(value, _MAX_QUOTE)
        return text or None


class PhaseNoteOut(BaseModel):
    phase: str = Field(min_length=1)
    note: str = ""

    @field_validator("phase", "note", mode="before")
    @classmethod
    def _t(cls, value):
        return _text(value)


def _items(value) -> list:
    """A list of {point, quote}; bare strings become items, junk is skipped."""
    if isinstance(value, (str, dict)):
        value = [value]
    out = []
    for entry in value if isinstance(value, list) else []:
        if isinstance(entry, str) and entry.strip():
            out.append({"point": entry})
        elif isinstance(entry, dict) and str(entry.get("point", "")).strip():
            out.append(entry)
    return out[:3]


def _notes(value) -> list:
    out = []
    for entry in value if isinstance(value, list) else []:
        if isinstance(entry, dict) and str(entry.get("phase", "")).strip():
            out.append(entry)
    return out[:6]


def _steps(value) -> list[str]:
    if isinstance(value, str):
        value = [value]
    return [_text(v, 160) for v in value if _text(v, 160)][:3] if isinstance(value, list) else []


Items = Annotated[list[ItemOut], BeforeValidator(_items)]
Notes = Annotated[list[PhaseNoteOut], BeforeValidator(_notes)]
Steps = Annotated[list[str], BeforeValidator(_steps)]


class ReportOut(BaseModel):
    verdict: str = ""
    dimensions: dict[str, DimensionOut]
    strengths: Items = Field(default_factory=list)
    improvements: Items = Field(default_factory=list)
    phase_notes: Notes = Field(default_factory=list)
    next_steps: Steps = Field(default_factory=list)

    @field_validator("verdict", mode="before")
    @classmethod
    def _verdict(cls, value):
        return _text(value, 200)

    @field_validator("dimensions", mode="before")
    @classmethod
    def _dims(cls, value):
        if not isinstance(value, dict):
            raise ValueError("dimensions must be an object keyed by dimension name")
        return {k: v for k, v in value.items() if k in DIMENSIONS and isinstance(v, dict)}

    @model_validator(mode="after")
    def _enough_scored(self):
        scored = [d for d in self.dimensions.values() if d.score is not None]
        if len(scored) < 2:
            raise ValueError("score at least two dimensions (communication, structure, technical_depth, role_relevance)")
        return self
