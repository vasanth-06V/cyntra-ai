import json
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app.core.errors import AppError, install_error_handlers
from app.core.middleware import RequestContextMiddleware


def _app() -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    class Body(BaseModel):
        name: str = Field(min_length=3)

    @app.get("/coded")
    async def coded():
        raise AppError(412, "key_missing", "No gemini key configured")

    @app.get("/plain")
    async def plain():
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Resume not found")

    @app.post("/validate")
    async def validate(body: Body):
        return {"ok": True}

    @app.get("/boom")
    async def boom():
        raise RuntimeError("secret internal detail")

    return app


ORIGIN = {"Origin": "http://localhost:3000"}


def test_app_error_uses_the_envelope_and_keeps_detail_for_old_clients():
    r = TestClient(_app()).get("/coded")
    body = r.json()
    assert r.status_code == 412
    assert body["error"]["code"] == "key_missing"
    assert body["error"]["message"] == "No gemini key configured"
    assert body["detail"] == "No gemini key configured"
    assert body["error"]["request_id"] == r.headers["x-request-id"]


def test_plain_http_exceptions_get_a_default_code_from_their_status():
    r = TestClient(_app()).get("/plain")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_validation_errors_become_readable_text_with_field_details():
    r = TestClient(_app()).post("/validate", json={"name": "x"})
    body = r.json()
    assert r.status_code == 422
    assert body["error"]["code"] == "validation_failed"
    assert isinstance(body["detail"], str) and body["detail"]
    assert body["error"]["fields"][0]["field"] == "name"


def test_unhandled_errors_are_a_clean_500_that_keeps_cors_headers_and_hides_internals():
    r = TestClient(_app(), raise_server_exceptions=False).get("/boom", headers=ORIGIN)
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "internal_error"
    assert "secret internal detail" not in r.text
    # Without this the browser reports an opaque network error instead of our message.
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert r.headers["x-request-id"]


def test_an_incoming_request_id_is_reused_and_a_hostile_one_is_replaced():
    client = TestClient(_app())
    good = client.get("/coded", headers={"X-Request-ID": "abc12345-trace"})
    assert good.headers["x-request-id"] == "abc12345-trace"
    bad = client.get("/coded", headers={"X-Request-ID": "x\r\ninjected"})
    assert bad.headers["x-request-id"] != "x\r\ninjected"
    assert len(bad.headers["x-request-id"]) == 32


def test_each_request_writes_one_json_access_line_with_the_request_id():
    from app.core.jsonlog import JsonFormatter

    lines: list[str] = []

    class Capture(logging.Handler):
        def emit(self, record):  # formatted at emit time, inside the request context
            lines.append(self.format(record))

    handler = Capture()
    handler.setFormatter(JsonFormatter())
    access = logging.getLogger("app.access")
    access.addHandler(handler)
    access.setLevel(logging.INFO)
    try:
        r = TestClient(_app()).get("/plain")
    finally:
        access.removeHandler(handler)

    assert len(lines) == 1
    line = json.loads(lines[0])
    assert line["status"] == 404 and line["path"] == "/plain" and "ms" in line
    assert line["request_id"] == r.headers["x-request-id"]
