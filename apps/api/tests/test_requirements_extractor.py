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
    async def fake_complete_text(user_id, provider, messages):
        return '{"must_have": ["Python"]}'

    monkeypatch.setattr(requirements_extractor, "complete_text", fake_complete_text)

    result = await extract_requirements("user-1", "gemini", "some JD text")

    assert result == {
        "must_have": ["Python"],
        "nice_to_have": [],
        "experience_level": "unspecified",
        "title": "",
    }
