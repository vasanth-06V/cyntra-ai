"""Re-embeds stored vectors that were made with an older embedding model or
settings. RUN BY THE PROJECT OWNER ONLY.

Every resume chunk and question-bank row records the embedding version it was
made with (`embed_version`). When the model, dimensions or task types change
(app/llm/models.py::EMBEDDING_VERSION), old vectors live in a different space
and must be regenerated. This finds the rows whose version differs from the
current one and re-embeds them in batches of 100 (one request per batch).

    set GEMINI_API_KEY=...             # PowerShell: $env:GEMINI_API_KEY="..."
    python -m scripts.reembed          # dry run: just counts what is stale
    python -m scripts.reembed --apply  # re-embed (uses embedding quota: 1 request per 100 rows)

It uses the key from the environment, never one from the database.
"""

import argparse
import asyncio
import os
import sys
from collections.abc import Awaitable, Callable

from app.db import maintenance
from app.interviews.question_bank import embedding_text
from app.llm.models import EMBEDDING_VERSION
from app.providers.gemini import GeminiAdapter

BATCH = 100
SPACING_SECONDS = 1.0


async def reembed_rows(
    fetch: Callable[[int], Awaitable[list[dict]]],
    text_of: Callable[[dict], str],
    embed: Callable[[list[str]], Awaitable[list[list[float]]]],
    store: Callable[[str, list[float]], Awaitable[None]],
    batch: int = BATCH,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    apply: bool = True,
) -> dict:
    """Loops until nothing stale is left: fetch a batch, embed it, store it.
    A batch that fails stops the run (nothing is half-written: each row is
    updated only after its vector arrived). Dry runs only count the first batch."""
    done = requests = 0
    while True:
        rows = await fetch(batch)
        if not rows:
            break
        if not apply:
            return {"stale_at_least": len(rows), "updated": 0, "requests": 0}
        if requests:
            await sleep(SPACING_SECONDS)
        vectors = await embed([text_of(r) for r in rows])
        requests += 1
        for row, vector in zip(rows, vectors):
            await store(row["id"], vector)
        done += len(rows)
    return {"stale_at_least": done, "updated": done, "requests": requests}


async def main() -> int:
    parser = argparse.ArgumentParser(description="Re-embed stale vectors (owner-run).")
    parser.add_argument("--apply", action="store_true", help="actually re-embed (default: dry run)")
    args = parser.parse_args()

    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        print("Set GEMINI_API_KEY in the environment first (keys are never read from the database).")
        return 2

    adapter = GeminiAdapter()

    async def embed(texts: list[str]) -> list[list[float]]:
        return await adapter.embed_many(key, texts, kind="doc")

    print(f"Current embedding version: {EMBEDDING_VERSION}  ({'APPLY' if args.apply else 'dry run'})")

    chunks = await reembed_rows(
        fetch=lambda n: maintenance.stale_chunks(EMBEDDING_VERSION, n),
        text_of=lambda r: r["content"],
        embed=embed,
        store=lambda i, v: maintenance.set_chunk_embedding(i, v, EMBEDDING_VERSION),
        apply=args.apply,
    )
    print(f"resume_chunks:  {chunks}")

    questions = await reembed_rows(
        fetch=lambda n: maintenance.stale_questions(EMBEDDING_VERSION, n),
        text_of=lambda r: embedding_text(r["type"], r["question"], r.get("topic"), r.get("tags")),
        embed=embed,
        store=lambda i, v: maintenance.set_question_embedding(i, v, EMBEDDING_VERSION),
        apply=args.apply,
    )
    print(f"question_bank:  {questions}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
