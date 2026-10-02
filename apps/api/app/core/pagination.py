from dataclasses import dataclass

from fastapi import Query

MAX_PAGE_SIZE = 200


@dataclass(frozen=True)
class Page:
    limit: int
    offset: int


def page_params(
    limit: int = Query(50, ge=1, le=MAX_PAGE_SIZE), offset: int = Query(0, ge=0)
) -> Page:
    return Page(limit=limit, offset=offset)


def large_page_params(
    limit: int = Query(200, ge=1, le=MAX_PAGE_SIZE), offset: int = Query(0, ge=0)
) -> Page:
    """For admin lists that the UI loads whole (the question bank)."""
    return Page(limit=limit, offset=offset)
