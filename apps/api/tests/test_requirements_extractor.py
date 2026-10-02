import pytest

from app.ats import requirements_extractor
from app.ats.requirements_extractor import _extract_json, extract_requirements


def test_extract_json_parses_plain_json():
    data = _extract_json('{"must_have": ["Python"], "title": "Backend Engineer"}')
    assert data == {"must_have": ["Python"], "title": "Backend Engineer"}


def test_extract_json_strips_markdown_fences():
    text = '```json\n{"must_have": ["SQL"]}\n```'
    assert _extract_json(text) == {"must_have": ["SQL"]}


def test_extract_json_finds_json_amid_extra_commentary():
    text = 'Sure, here is the JSON:\n{"must_have": ["Go"]}\nLet me know if you need more.'
    assert _extract_json(text) == {"must_have": ["Go"]}


def test_extract_json_raises_when_no_json_present():
    with pytest.raises(ValueError, match="No JSON object found"):
        _extract_json("I couldn't find any requirements.")


@pytest.mark.asyncio
async def test_extract_requirements_fills_in_defaults_for_missing_fields(monkeypatch):
    seen = {}

    async def fake_complete(user_id, provider, messages, options=None):
        seen["options"] = options
        return '{"must_have": ["Python"]}'

    monkeypatch.setattr(requirements_extractor.gateway, "complete", fake_complete)

    result = await extract_requirements("user-1", "gemini", "some JD text")

    assert result == {
        "must_have": ["Python"],
        "nice_to_have": [],
        "experience_level": "unspecified",
        "title": "",
    }

    # Structured + deterministic + bounded.
    options = seen["options"]
    assert options.task == "extract"
    assert options.json_mode is True
    assert options.temperature == 0.0
    assert options.max_output_tokens is not None


@pytest.mark.asyncio
async def test_same_jd_is_served_from_cache_and_jd_is_truncated(monkeypatch):
    requirements_extractor._cache = requirements_extractor.TTLCache(ttl_seconds=60)
    calls = []

    async def fake_complete(user_id, provider, messages, options=None):
        calls.append(messages[0].content)
        return '{"must_have": ["Go"]}'

    monkeypatch.setattr(requirements_extractor.gateway, "complete", fake_complete)
    jd = "word " * 20000

    first = await extract_requirements("u1", "gemini", jd)
    second = await extract_requirements("u1", "gemini", jd)
    await extract_requirements("u2", "gemini", jd)  # other user: no sharing

    assert first == second
    assert len(calls) == 2
    assert len(calls[0]) < 1500 * 4 + 600  # JD capped at its budget
