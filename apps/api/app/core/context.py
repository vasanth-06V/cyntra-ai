"""Per-request context (request id, user id), carried in contextvars so any
code — logging, error handlers, the LLM gateway — can read it without it
being passed through every function."""

from contextvars import ContextVar

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_user_id: ContextVar[str | None] = ContextVar("user_id", default=None)


def get_request_id() -> str | None:
    return _request_id.get()


def set_request_id(value: str | None):
    return _request_id.set(value)


def get_user_id() -> str | None:
    return _user_id.get()


def set_user_id(value: str | None):
    return _user_id.set(value)
