"""Typed shapes for every JSON object a model is asked to produce. Models are
sloppy (a string where a list was asked for, nested objects, missing keys), so
each schema coerces what it safely can and rejects what it can't."""

from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, field_validator

_MAX_TERMS = 15


def _clean_list(value) -> list[str]:
    """Keep non-empty scalar strings, capped; a bare string becomes a list."""
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    cleaned = [str(v).strip() for v in value if isinstance(v, (str, int, float)) and str(v).strip()]
    return cleaned[:_MAX_TERMS]


TermList = Annotated[list[str], BeforeValidator(_clean_list)]


class RequirementsOut(BaseModel):
    must_have: TermList = Field(default_factory=list)
    nice_to_have: TermList = Field(default_factory=list)
    experience_level: str = "unspecified"
    title: str = ""

    @field_validator("experience_level", mode="before")
    @classmethod
    def _level(cls, value):
        return str(value).strip() if value else "unspecified"

    @field_validator("title", mode="before")
    @classmethod
    def _title(cls, value):
        return str(value).strip() if value else ""


class SetupOut(BaseModel):
    """The interview setup call: a distilled brief plus the spoken opening."""

    brief: str = ""
    opening: str = Field(min_length=1)

    @field_validator("opening", "brief", mode="before")
    @classmethod
    def _text(cls, value):
        return str(value).strip() if value is not None else ""
