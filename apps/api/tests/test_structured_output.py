import json

import pytest
from pydantic import BaseModel

from app.llm import gateway
from app.llm.options import LLMOptions
from app.providers.base import Message, MessageRole

from tests.helpers import completion

MESSAGES = [Message(MessageRole.USER, "give me json")]


class Shape(BaseModel):
    name: str
    count: int


def script(monkeypatch, *replies):
    """Replaces complete_full; each reply is a Completion. Returns the call log."""
    calls = []

    async def fake(user_id, provider, messages, options=None):
        calls.append((list(messages), options))
        return replies[min(len(calls) - 1, len(replies) - 1)]

    monkeypatch.setattr(gateway, "complete_full", fake)
    return calls


@pytest.mark.asyncio
async def test_valid_json_is_one_call_and_forces_json_mode(monkeypatch):
    calls = script(monkeypatch, completion('{"name": "a", "count": 2}'))
    result = await gateway.complete_structured("u", "gemini", MESSAGES, Shape, LLMOptions(task="extract"))
    assert result == Shape(name="a", count=2)
    assert len(calls) == 1 and calls[0][1].json_mode is True


@pytest.mark.asyncio
async def test_invalid_output_gets_one_repair_that_names_the_problem(monkeypatch):
    calls = script(monkeypatch, completion('{"name": "a", "count": "many"}'), completion('{"name": "a", "count": 3}'))
    result = await gateway.complete_structured("u", "gemini", MESSAGES, Shape)
    assert result.count == 3 and len(calls) == 2
    repair_messages = calls[1][0]
    assert repair_messages[-2].role == MessageRole.ASSISTANT
    assert "count" in repair_messages[-1].content  # the validation problem is spelled out


@pytest.mark.asyncio
async def test_a_reply_cut_off_by_the_cap_is_retried_with_more_room_not_a_lecture(monkeypatch):
    calls = script(monkeypatch, completion('{"name": "a", "cou', finish="length"), completion('{"name": "a", "count": 1}'))
    await gateway.complete_structured("u", "gemini", MESSAGES, Shape, LLMOptions(max_output_tokens=100))
    assert calls[1][1].max_output_tokens == 200
    assert calls[1][0] == MESSAGES  # same prompt, no repair message


@pytest.mark.asyncio
async def test_two_failures_raise_with_the_first_attempt_preserved(monkeypatch):
    script(monkeypatch, completion('{"name": "first try"'), completion("not json"))
    with pytest.raises(gateway.StructuredOutputError) as exc:
        await gateway.complete_structured("u", "gemini", MESSAGES, Shape)
    assert exc.value.raw == '{"name": "first try"'
    assert exc.value.problem


@pytest.mark.asyncio
async def test_validity_outcomes_are_logged_per_feature_and_prompt_version(monkeypatch, caplog):
    import logging

    script(monkeypatch, completion("nope"), completion('{"name": "a", "count": 1}'))
    with caplog.at_level(logging.INFO, logger="app.llm"):
        await gateway.complete_structured(
            "u", "gemini", MESSAGES, Shape,
            LLMOptions(feature="ats_requirements", prompt_id="ats.requirements", prompt_version="1"),
        )
    record = next(r for r in caplog.records if r.getMessage() == "structured_output")
    assert record.outcome == "repaired" and record.feature == "ats_requirements" and record.prompt_version == "1"
