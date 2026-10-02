"""Rate-safe live smoke test for the LLM layer. RUN BY THE PROJECT OWNER ONLY.

It turns the facts we could not verify offline into recorded evidence:
  * what Gemini's 400 / 404 / (429 if you hit one) error bodies really look like
  * whether `thinkingConfig` is accepted for our model alias, and how many
    thought tokens a short reply costs
  * time to first token, finish reasons, usage fields
  * that batched embeddings come back with the expected shape and dimensions
  * (optional) the same basics for Groq and Claude

Budget: at most ~10 Gemini requests (default hard cap 10), spaced 5 s apart so
the free tier's 15 requests/minute can never be hit, and it stops at the first
429. It uses a key you pass in the environment -- never one from the database --
and the key never appears in output or in recorded fixtures.

Usage (from apps/api, with the venv active):

    set GEMINI_API_KEY=...            # PowerShell: $env:GEMINI_API_KEY="..."
    python -m scripts.llm_smoke                # run and print a report
    python -m scripts.llm_smoke --record       # also save redacted fixtures to tests/fixtures/
    python -m scripts.llm_smoke --groq --claude   # also probe those (need GROQ_API_KEY / ANTHROPIC_API_KEY)

Nothing here is imported by the app or by the test suite.
"""

import argparse
import asyncio
import json
import math
import os
import re
import sys
import time
from pathlib import Path

import httpx

from app.llm.models import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL, gemini_traits, model_for
from app.llm.options import LLMOptions, Usage
from app.providers import gemini
from app.providers.base import Message, MessageRole, ProviderError
from app.providers.gemini import BASE_URL, GeminiAdapter

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "gemini"
SPACING_SECONDS = 5.0
MAX_REQUESTS = 10

USER = [Message(MessageRole.USER, "Reply with exactly: pong")]


class Budget:
    """Hard cap on live requests; every request goes through `spend()`."""

    def __init__(self, limit: int):
        self.limit, self.used = limit, 0

    async def spend(self, label: str) -> None:
        if self.used >= self.limit:
            raise SystemExit(f"Request budget ({self.limit}) reached before: {label}")
        if self.used:
            await asyncio.sleep(SPACING_SECONDS)
        self.used += 1
        print(f"  [{self.used}/{self.limit}] {label}")


def redact(text: str, secrets: list[str]) -> str:
    for secret in secrets:
        if secret:
            text = text.replace(secret, "<redacted>")
    return re.sub(r"AIza[0-9A-Za-z_\-]{20,}", "<redacted>", text)


def save_fixture(name: str, status: int, headers: dict, body, secrets: list[str]) -> None:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    keep = {k: v for k, v in headers.items() if k.lower() in {"retry-after", "content-type"}}
    payload = json.dumps({"scenario": name, "status": status, "headers": keep, "body": body}, indent=2)
    (FIXTURE_DIR / f"{name}.json").write_text(redact(payload, secrets), encoding="utf-8")
    print(f"    recorded tests/fixtures/gemini/{name}.json")


async def raw_post(client: httpx.AsyncClient, url: str, key: str, body: dict) -> httpx.Response:
    return await client.post(url, headers={"x-goog-api-key": key, "content-type": "application/json"}, json=body, timeout=40)


def summarize_error(response: httpx.Response) -> str:
    try:
        error = response.json().get("error", {})
        detail_types = [str(d.get("@type", "")).rsplit(".", 1)[-1] for d in error.get("details", []) if isinstance(d, dict)]
        return f"HTTP {response.status_code} {error.get('status')}: {str(error.get('message'))[:140]} | detail types: {detail_types or 'none'}"
    except Exception:
        return f"HTTP {response.status_code}: {response.text[:140]}"


async def gemini_checks(key: str, record: bool, budget: Budget) -> list[tuple[str, str]]:
    results: list[tuple[str, str]] = []
    adapter = GeminiAdapter()
    model = model_for("gemini", "chat")
    traits = gemini_traits(model)
    secrets = [key]
    print(f"\nGemini  model={model}  thinkingConfig={traits['thinking_config']}  allowance={traits['allowance']}")

    async def attempt(name: str, coro):
        try:
            results.append((name, await coro))
        except SystemExit:
            raise
        except ProviderError as exc:
            results.append((name, f"FAILED {type(exc).__name__}: {str(exc)[:160]}"))
            if getattr(exc, "kind", None) is not None:  # a rate limit: stop probing this key
                raise SystemExit("Hit a rate limit -- stopping early so nothing else is spent.")

    async def validate():
        await budget.spend("validate key (lists models, no generation quota)")
        return "key accepted" if await adapter.validate(key) else "key REJECTED"

    async def plain():
        await budget.spend("non-streaming reply")
        usage = Usage()
        started = time.perf_counter()
        text = "".join([c async for c in adapter.chat(key, USER, stream=False, options=LLMOptions(task="chat", max_output_tokens=30), usage=usage)])
        ms = round((time.perf_counter() - started) * 1000)
        thinking_sent = model not in gemini._thinking_rejected and traits["thinking_config"] is not None
        return (
            f"text={text!r} finish={usage.finish_reason} in={usage.input_tokens} out={usage.output_tokens} "
            f"thought={usage.thought_tokens} latency={ms}ms thinkingConfig {'ACCEPTED' if thinking_sent else 'REJECTED/none (auto-dropped)'}"
        )

    async def streaming():
        await budget.spend("streaming reply (time to first token)")
        usage = Usage()
        pieces = [c async for c in adapter.chat(key, USER, stream=True, options=LLMOptions(task="chat", max_output_tokens=30), usage=usage)]
        return f"chunks={len(pieces)} ttft={usage.ttft_ms}ms finish={usage.finish_reason} thought={usage.thought_tokens}"

    async def json_mode():
        await budget.spend("JSON mode")
        usage = Usage()
        text = "".join([c async for c in adapter.chat(key, [Message(MessageRole.USER, 'Return {"ok": true} as JSON.')], stream=False, options=LLMOptions(task="extract", json_mode=True, max_output_tokens=40), usage=usage)])
        try:
            json.loads(text)
            return f"valid JSON {text!r} finish={usage.finish_reason}"
        except ValueError:
            return f"NOT valid JSON: {text!r}"

    async def embeddings():
        await budget.spend("embeddings (3 texts, doc + query kinds = 2 requests)")
        docs = await adapter.embed_many(key, ["python developer", "kubernetes", "sql"], kind="doc")
        await budget.spend("embeddings query kind")
        queries = await adapter.embed_many(key, ["experience with python"], kind="query")
        dims = {len(v) for v in docs + queries}
        norms = [round(math.sqrt(sum(x * x for x in v)), 4) for v in docs + queries]
        return f"dims={sorted(dims)} (expected {EMBEDDING_DIMENSIONS}) norms={norms} model={EMBEDDING_MODEL}"

    await attempt("validate", validate())
    await attempt("plain reply", plain())
    await attempt("streaming", streaming())
    await attempt("json mode", json_mode())
    await attempt("embeddings", embeddings())

    async with httpx.AsyncClient() as client:
        await budget.spend("error probe: invalid API key (expect 400 API_KEY_INVALID)")
        bad = await raw_post(client, f"{BASE_URL}/models/{model}:generateContent", "AIzaSyINVALID-KEY-FOR-PROBING-0000000000", {"contents": [{"parts": [{"text": "hi"}]}]})
        results.append(("bad key error", summarize_error(bad)))
        if record:
            save_fixture("error_bad_api_key", bad.status_code, dict(bad.headers), bad.json(), secrets)

        await budget.spend("error probe: unknown model (expect 404)")
        missing = await raw_post(client, f"{BASE_URL}/models/definitely-not-a-model:generateContent", key, {"contents": [{"parts": [{"text": "hi"}]}]})
        results.append(("unknown model error", summarize_error(missing)))
        if record:
            save_fixture("error_model_not_found", missing.status_code, dict(missing.headers), missing.json(), secrets)

        await budget.spend("error probe: thinkingConfig value (does the API accept thinkingLevel?)")
        probe = await raw_post(client, f"{BASE_URL}/models/{model}:generateContent", key, {
            "contents": [{"parts": [{"text": "hi"}]}],
            "generationConfig": {"maxOutputTokens": 20, "thinkingConfig": {"thinkingLevel": "minimal"}},
        })
        results.append(("thinkingLevel=minimal", "accepted" if probe.status_code == 200 else summarize_error(probe)))
        if record:
            save_fixture("generate_with_thinking_level" if probe.status_code == 200 else "error_thinking_level_rejected",
                         probe.status_code, dict(probe.headers), probe.json(), secrets)

    return results


async def groq_checks(key: str, budget: Budget) -> list[tuple[str, str]]:
    from app.providers.groq import GroqAdapter

    adapter, results = GroqAdapter(), []
    await budget.spend("Groq: reply")
    usage = Usage()
    try:
        text = "".join([c async for c in adapter.chat(key, USER, stream=False, options=LLMOptions(task="chat", max_output_tokens=20), usage=usage)])
        results.append(("groq reply", f"text={text!r} finish={usage.finish_reason} model={usage.model}"))
    except ProviderError as exc:
        results.append(("groq reply", f"FAILED {type(exc).__name__}: {str(exc)[:160]}"))
    return results


async def claude_checks(key: str, budget: Budget) -> list[tuple[str, str]]:
    from app.providers.claude import ClaudeAdapter

    adapter, results = ClaudeAdapter(), []
    await budget.spend("Claude: reply")
    usage = Usage()
    try:
        text = "".join([c async for c in adapter.chat(key, USER, stream=False, options=LLMOptions(task="chat", max_output_tokens=20), usage=usage)])
        results.append(("claude reply", f"text={text!r} finish={usage.finish_reason} model={usage.model}"))
    except ProviderError as exc:
        results.append(("claude reply", f"FAILED {type(exc).__name__}: {str(exc)[:160]}"))
    return results


async def main() -> int:
    parser = argparse.ArgumentParser(description="Rate-safe live LLM smoke test (owner-run).")
    parser.add_argument("--record", action="store_true", help="save redacted response fixtures to tests/fixtures/gemini/")
    parser.add_argument("--groq", action="store_true", help="also probe Groq (needs GROQ_API_KEY)")
    parser.add_argument("--claude", action="store_true", help="also probe Claude (needs ANTHROPIC_API_KEY)")
    parser.add_argument("--max-requests", type=int, default=MAX_REQUESTS)
    args = parser.parse_args()

    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        print("Set GEMINI_API_KEY in the environment first (this script never reads keys from the database).")
        return 2

    budget = Budget(args.max_requests)
    print(f"Spacing {SPACING_SECONDS:.0f}s between requests; hard cap {budget.limit}. Ctrl+C to stop.")
    results = await gemini_checks(key, args.record, budget)
    if args.groq and os.environ.get("GROQ_API_KEY"):
        results += await groq_checks(os.environ["GROQ_API_KEY"], budget)
    if args.claude and os.environ.get("ANTHROPIC_API_KEY"):
        results += await claude_checks(os.environ["ANTHROPIC_API_KEY"], budget)

    print("\n=== Report ===")
    for name, outcome in results:
        print(f"- {name}: {redact(outcome, [key])}")
    print(f"\nLive requests used: {budget.used}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
