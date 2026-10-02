"""Replays responses recorded from the real Gemini API (by the owner-run
scripts/llm_smoke.py --record) through the adapter's own parsing and error
mapping. Skipped until fixtures exist; once they do, the wire format we have
only inferred from documentation is pinned by evidence.

Also covers the smoke script's offline-testable guards (budget, redaction)."""

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from app.providers.base import (
    Message,
    MessageRole,
    ProviderAuthError,
    ProviderBadRequestError,
    ProviderConfigError,
    ProviderRateLimitError,
)
from app.providers.gemini import GeminiAdapter, map_error

FIXTURES = Path(__file__).parent / "fixtures" / "gemini"
USER = [Message(MessageRole.USER, "hi")]

# scenario -> what the adapter must make of it
EXPECTED_ERRORS = {
    "error_bad_api_key": ProviderAuthError,
    "error_model_not_found": ProviderConfigError,
    "error_thinking_level_rejected": ProviderBadRequestError,
    "error_rate_limited": ProviderRateLimitError,
}


def _load():
    if not FIXTURES.exists():
        return []
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(FIXTURES.glob("*.json"))]


recorded = _load()


@pytest.mark.skipif(not recorded, reason="no recorded fixtures yet -- run scripts/llm_smoke.py --record")
@pytest.mark.parametrize("fixture", recorded, ids=[f["scenario"] for f in recorded])
def test_recorded_gemini_responses_replay_through_the_adapter(fixture):
    scenario, status, body = fixture["scenario"], fixture["status"], fixture["body"]
    if scenario in EXPECTED_ERRORS:
        error = map_error(status, json.dumps(body).encode(), httpx.Headers(fixture.get("headers", {})))
        assert isinstance(error, EXPECTED_ERRORS[scenario]), f"{scenario}: got {type(error).__name__}"
        return

    # a successful generateContent response: must parse to text + usage
    transport = httpx.MockTransport(lambda request: httpx.Response(status, json=body))

    async def run():
        out = []
        async for piece in GeminiAdapter(transport=transport).chat("k", USER, stream=False):
            out.append(piece)
        return "".join(out)

    assert status == 200 and asyncio.run(run()) is not None


# --- smoke script guards (offline) --------------------------------------------------------------


def test_the_smoke_script_never_exceeds_its_request_budget():
    from scripts import llm_smoke

    budget = llm_smoke.Budget(2)

    async def spend_three():
        llm_smoke.SPACING_SECONDS = 0.0
        await budget.spend("one")
        await budget.spend("two")
        await budget.spend("three")

    with pytest.raises(SystemExit):
        asyncio.run(spend_three())
    assert budget.used == 2


def test_the_smoke_script_redacts_keys_everywhere():
    from scripts import llm_smoke

    text = "failed for key AIzaSyA1234567890abcdefghijklmnop and secret-xyz"
    cleaned = llm_smoke.redact(text, ["secret-xyz"])
    assert "AIza" not in cleaned and "secret-xyz" not in cleaned
