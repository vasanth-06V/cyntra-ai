from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator


def _uuid_string(value: str) -> str:
    UUID(value)  # ValueError -> FastAPI answers 422 instead of Postgres failing with a 500
    return value


# A path/body id that must be a UUID (the form every table uses).
UuidStr = Annotated[str, AfterValidator(_uuid_string)]
