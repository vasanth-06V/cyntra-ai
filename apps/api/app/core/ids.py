from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator


def _uuid_string(value: str) -> str:
    parsed = UUID(value)  # ValueError -> FastAPI answers 422 instead of Postgres failing with a 500
    if str(parsed) != value.lower():
        # `urn:uuid:...`, braces or missing hyphens parse in Python but Postgres rejects them.
        raise ValueError("not a canonical UUID")
    return value


# A path/body id that must be a UUID (the form every table uses).
UuidStr = Annotated[str, AfterValidator(_uuid_string)]
