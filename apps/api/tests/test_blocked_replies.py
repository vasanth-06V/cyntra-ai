import pytest
from fastapi import HTTPException

from app.llm import gateway
from app.providers.base import ProviderBlockedError

from tests.test_gateway import MESSAGES, USER, env  # noqa: F401  (fixture reuse)


async def _drain(agen):
    return [c async for c in agen]


@pytest.mark.asyncio
async def test_gateway_turns_a_blocked_reply_into_a_clear_422_without_failover(env):  # noqa: F811
    env.adapter.outcomes = {"primary-key": [ProviderBlockedError("blocked")]}

    with pytest.raises(HTTPException) as exc:
        await gateway.complete(USER, "gemini", MESSAGES)

    assert exc.value.status_code == 422
    assert env.adapter.calls == ["primary-key"]  # a different key wouldn't help


@pytest.mark.asyncio
async def test_gateway_stream_blocked_before_output_is_a_422(env):  # noqa: F811
    env.adapter.outcomes = {"primary-key": [ProviderBlockedError("blocked")]}

    with pytest.raises(HTTPException) as exc:
        await _drain(gateway.stream(USER, "gemini", MESSAGES))

    assert exc.value.status_code == 422
