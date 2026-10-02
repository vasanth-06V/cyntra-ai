import asyncio

import pytest

from app.core import background


@pytest.mark.asyncio
async def test_scheduled_work_runs_and_drain_waits_for_it():
    done = []

    async def work():
        await asyncio.sleep(0.01)
        done.append(1)

    assert background.schedule(work(), name="w") is True
    assert done == []
    await background.drain()
    assert done == [1]


@pytest.mark.asyncio
async def test_a_failing_task_is_logged_not_raised_and_does_not_block_others(caplog):
    async def boom():
        raise RuntimeError("nope")

    ran = []

    async def fine():
        ran.append(1)

    background.schedule(boom(), name="boom")
    background.schedule(fine(), name="fine")
    await background.drain()
    assert ran == [1]
    assert any("Background task boom failed" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_only_one_task_per_key_runs_at_a_time():
    gate = asyncio.Event()
    runs = []

    async def work(tag):
        runs.append(tag)
        await gate.wait()

    assert background.schedule(work("first"), name="a", key="k") is True
    assert background.schedule(work("second"), name="b", key="k") is False  # dropped, not queued
    await asyncio.sleep(0)
    gate.set()
    await background.drain()
    assert runs == ["first"]
    assert background.schedule(work("third"), name="c", key="k") is True  # the key is free again
    await background.drain()
    assert runs == ["first", "third"]


@pytest.mark.asyncio
async def test_a_turn_returns_without_waiting_for_the_summary(monkeypatch):
    from datetime import UTC, datetime

    from app.interviews import service

    release = asyncio.Event()
    finished = []

    async def slow_summary(*a):
        await release.wait()
        finished.append(1)

    async def value(v):
        return v

    interview = {
        "id": "i-1", "type": "behavioral", "status": "in_progress", "phase": "warm_up", "jd_text": "JD",
        "brief": "b", "provider": "gemini", "resume_id": "r", "running_summary": None,
        "selected_question_ids": [], "started_at": datetime.now(UTC).isoformat(),
    }

    async def fake_complete(*a, **k):
        return "Next question?"

    monkeypatch.setattr(service, "_get_owned_interview", lambda *a: value(interview))
    monkeypatch.setattr(service, "_update_interview", lambda *a: value(None))
    monkeypatch.setattr(service, "_next_turn_index", lambda *a: value(2))
    monkeypatch.setattr(service, "_append_transcript", lambda *a: value(None))
    monkeypatch.setattr(service, "_recent_turns", lambda *a: value([{"speaker": "ai", "text": "Hi"}]))
    monkeypatch.setattr(service.summarizer, "maybe_update_summary", slow_summary)
    monkeypatch.setattr(service.gateway, "complete", fake_complete)

    result = await asyncio.wait_for(service.submit_turn("u", "i-1", "answer"), timeout=2)

    assert result["message"] == "Next question?" and finished == []  # reply is out; summary still running
    release.set()
    await background.drain()
    assert finished == [1]
