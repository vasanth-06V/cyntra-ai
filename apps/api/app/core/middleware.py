"""Request context middleware (pure ASGI, so streaming responses are not
buffered): assigns a request id, times the request, writes one structured
access-log line, and turns any unhandled exception into the standard error
envelope — inside the CORS layer, so the browser can read it."""

import logging
import re
import time
import uuid

from app.core.context import set_request_id, set_user_id
from app.core.errors import internal_error_response

logger = logging.getLogger("app.access")

_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
REQUEST_ID_HEADER = "x-request-id"


class RequestContextMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = dict(scope.get("headers") or []).get(REQUEST_ID_HEADER.encode(), b"").decode()
        request_id = incoming if _SAFE_ID.match(incoming) else uuid.uuid4().hex
        token_req, token_user = set_request_id(request_id), set_user_id(None)

        started = time.perf_counter()
        status_holder = {"status": 500, "started": False}

        async def send_with_id(message):
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                status_holder["started"] = True
                headers = list(message.get("headers") or [])
                headers.append((REQUEST_ID_HEADER.encode(), request_id.encode()))
                message = {**message, "headers": headers}
            await send(message)

        try:
            try:
                await self.app(scope, receive, send_with_id)
            except Exception:
                logger.exception("Unhandled error", extra={"path": scope.get("path")})
                if status_holder["started"]:
                    raise  # response already begun; nothing safe to send
                status_holder["status"] = 500
                await internal_error_response()(scope, receive, send_with_id)
        finally:
            logger.info(
                "request",
                extra={
                    "method": scope.get("method"),
                    "path": scope.get("path"),
                    "status": status_holder["status"],
                    "ms": round((time.perf_counter() - started) * 1000, 1),
                },
            )
