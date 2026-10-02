"""One error shape for the whole API.

Every error response looks like:

    {"error": {"code": "key_missing", "message": "...", "request_id": "..."},
     "detail": "..."}

`code` is stable and machine-readable (the UI can branch on it); `message` is
safe to show to a user; `detail` repeats the message for older clients.

`AppError` subclasses HTTPException, so existing `raise HTTPException(...)`
call sites, `except HTTPException` handlers and tests keep working; they just
get a default code derived from the status.
"""

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.context import get_request_id

logger = logging.getLogger(__name__)

_DEFAULT_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    412: "precondition_failed",
    413: "payload_too_large",
    422: "validation_failed",
    429: "rate_limited",
    500: "internal_error",
    502: "bad_gateway",
    503: "service_unavailable",
    504: "timeout",
}


class AppError(HTTPException):
    def __init__(self, status_code: int, code: str, message: str, headers: dict | None = None):
        super().__init__(status_code=status_code, detail=message, headers=headers)
        self.code = code


def code_for(exc: StarletteHTTPException) -> str:
    return getattr(exc, "code", None) or _DEFAULT_CODES.get(exc.status_code, "error")


def envelope(status_code: int, code: str, message: str, **extra) -> dict:
    body = {
        "error": {"code": code, "message": message, "request_id": get_request_id(), **extra},
        "detail": message,
    }
    return body


def _message(detail) -> str:
    return detail if isinstance(detail, str) else "Request failed"


async def _http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        envelope(exc.status_code, code_for(exc), _message(exc.detail)),
        status_code=exc.status_code,
        headers=getattr(exc, "headers", None),
    )


async def _validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    fields = [
        {"field": ".".join(str(p) for p in e.get("loc", []) if p != "body"), "message": e.get("msg", "")}
        for e in exc.errors()
    ]
    message = "; ".join(f["message"] for f in fields if f["message"]) or "Invalid request"
    return JSONResponse(
        envelope(422, "validation_failed", message, fields=fields),
        status_code=422,
    )


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_handler)


def internal_error_response() -> JSONResponse:
    """Used by the request-context middleware for anything unhandled."""
    return JSONResponse(
        envelope(500, "internal_error", "Something went wrong on our side. Please try again."),
        status_code=500,
    )
