import pytest
from fastapi import HTTPException

from app.chat import service


async def _async_none():
    return None


async def _async_value(value):
    return value


@pytest.fixture
def stored(monkeypatch):
    """Patches the DB-facing helpers; returns the messages appended."""
    appended: list[dict] = []

    async def fake_append(conversation_id, role, content, provider=None):
        appended.append({"role": role, "content": content, "provider": provider})
        return {}

    monkeypatch.setattr(service, "_require_owned_conversation", lambda *a, **kw: _async_none())
    monkeypatch.setattr(service, "_append_message", fake_append)
    monkeypatch.setattr(
        service,
        "list_messages",
        lambda *a, **kw: _async_value(
            [
                {"role": "user", "content": "earlier question"},
                {"role": "assistant", "content": "earlier answer"},
            ]
        ),
    )
    return appended


def _patch_gateway(monkeypatch, chunks=("Hello", ", ", "world!"), error: Exception | None = None):
    seen = {}

    async def fake_stream(user_id, provider, messages, options=None):
        seen.update(user_id=user_id, provider=provider, messages=messages, options=options)
        if error:
            raise error
        for c in chunks:
            yield c

    monkeypatch.setattr(service.gateway, "stream", fake_stream)
    return seen


async def _collect(agen):
    return [chunk async for chunk in agen]


@pytest.mark.asyncio
async def test_streams_the_reply_and_persists_both_messages(monkeypatch, stored):
    _patch_gateway(monkeypatch)

    chunks = await _collect(service.stream_reply("user-1", "conv-1", "gemini", "hi"))

    assert "".join(chunks) == "Hello, world!"
    assert stored[0] == {"role": "user", "content": "hi", "provider": None}
    assert stored[-1] == {"role": "assistant", "content": "Hello, world!", "provider": "gemini"}


@pytest.mark.asyncio
async def test_sends_prior_history_then_the_new_message_to_the_gateway(monkeypatch, stored):
    seen = _patch_gateway(monkeypatch)

    await _collect(service.stream_reply("user-1", "conv-1", "gemini", "new question"))

    contents = [m.content for m in seen["messages"]]
    assert contents == ["earlier question", "earlier answer", "new question"]
    assert seen["provider"] == "gemini"
    assert seen["options"].task == "chat"


@pytest.mark.asyncio
async def test_gateway_errors_propagate_and_no_assistant_message_is_saved(monkeypatch, stored):
    _patch_gateway(monkeypatch, error=HTTPException(status_code=503, detail="overloaded"))

    with pytest.raises(HTTPException) as exc:
        await _collect(service.stream_reply("user-1", "conv-1", "gemini", "hi"))

    assert exc.value.status_code == 503
    assert stored == []  # nothing is saved for a failed send, so a retry can't duplicate it


def test_router_returns_a_real_error_status_instead_of_a_broken_stream(monkeypatch):
    from fastapi.testclient import TestClient

    from app.core.security import AuthenticatedUser, get_current_user
    from app.main import app

    async def failing_reply(*args, **kwargs):
        raise HTTPException(status_code=503, detail="Gemini is temporarily overloaded")
        yield  # pragma: no cover -- makes this an async generator

    monkeypatch.setattr("app.chat.router.service.stream_reply", failing_reply)
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser("user-1", "a@b.com")
    try:
        response = TestClient(app).post(
            "/chat/conversations/11111111-1111-4111-8111-111111111111/messages",
            json={"provider": "gemini", "content": "hi"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["detail"] == "Gemini is temporarily overloaded"


@pytest.mark.asyncio
async def test_history_sent_to_the_model_is_windowed(monkeypatch):
    from app.chat import service

    rows = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"} for i in range(40)]
    sent = {}

    async def owned(*a):
        return {"id": "c"}

    async def listing(*a):
        return rows

    async def append(*a, **k):
        return {}

    async def fake_stream(user_id, provider, messages, options=None):
        sent["messages"] = messages
        yield "ok"

    monkeypatch.setattr(service, "_require_owned_conversation", owned)
    monkeypatch.setattr(service, "list_messages", listing)
    monkeypatch.setattr(service, "_append_message", append)
    monkeypatch.setattr(service.gateway, "stream", fake_stream)

    async for _ in service.stream_reply("u", "c", "gemini", "hello"):
        pass

    assert len(sent["messages"]) == 11  # last 10 + the new message
    assert sent["messages"][-1].content == "hello"
