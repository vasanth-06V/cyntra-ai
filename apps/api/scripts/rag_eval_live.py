"""Calibrates the ATS semantic window against the REAL embedding model.
RUN BY THE PROJECT OWNER ONLY (the assistant never runs it).

The offline eval (tests/rag_eval) uses a fake embedder, so it can check the
pipeline's structure but cannot say what similarity a real model gives a
relevant vs an unrelated chunk. This script measures exactly that on the golden
resumes/JDs and suggests values for LOW and HIGH in app/ats/semantic.py.

Budget: one embedding request per golden resume (6) + one per JD (2) = 8
requests, spaced 1 s apart (the embeddings free tier allows 100 RPM / 1,000 RPD).
The key comes from the environment, never from the database, and is never printed.

    set GEMINI_API_KEY=...            # PowerShell: $env:GEMINI_API_KEY="..."
    python -m scripts.rag_eval_live
"""

import asyncio
import os
import statistics
import sys

from app.ats.semantic import query_text
from app.providers.gemini import GeminiAdapter
from app.rag.resume_chunker import chunk_resume
from tests.rag_eval.golden import EVIDENCE, JDS, RESUMES

SPACING_SECONDS = 1.0
MAX_REQUESTS = 12


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return float("nan")
    k = (len(ordered) - 1) * pct
    low, high = int(k), min(int(k) + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (k - low)


def suggest_window(covered: list[float], uncovered: list[float]) -> dict:
    """LOW = where unrelated chunks stop (their 90th percentile); HIGH = where
    clearly relevant ones sit (the median of covered). Reports how far apart
    the two groups are, so you can see whether the model separates them."""
    low = round(percentile(uncovered, 0.90), 2)
    high = round(percentile(covered, 0.50), 2)
    return {
        "LOW": low,
        "HIGH": max(high, round(low + 0.05, 2)),
        "gap": round(percentile(covered, 0.10) - percentile(uncovered, 0.90), 3),
        "overlap": percentile(covered, 0.10) <= percentile(uncovered, 0.90),
    }


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))  # vectors are L2-normalized by the adapter


async def main() -> int:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        print("Set GEMINI_API_KEY in the environment first (keys are never read from the database).")
        return 2

    adapter, used = GeminiAdapter(), 0

    async def embed(texts: list[str], kind: str) -> list[list[float]]:
        nonlocal used
        if used >= MAX_REQUESTS:
            raise SystemExit("request budget reached")
        if used:
            await asyncio.sleep(SPACING_SECONDS)
        used += 1
        return await adapter.embed_many(key, texts, kind=kind)

    print(f"Embedding {len(RESUMES)} resumes and {len(JDS)} requirement sets with the live model...")
    resume_vectors = {}
    for name, text in RESUMES.items():
        chunks = chunk_resume(text)
        resume_vectors[name] = (chunks, await embed([c.content for c in chunks], "doc"))
    jd_vectors = {}
    for jd, req in JDS.items():
        terms = req["must_have"] + req["nice_to_have"]
        jd_vectors[jd] = (terms, await embed([query_text(t) for t in terms], "query"))

    covered: list[float] = []
    uncovered: list[float] = []
    by_pair = []
    for name, (chunks, vectors) in resume_vectors.items():
        for jd, (terms, queries) in jd_vectors.items():
            truth = EVIDENCE.get(name, {}).get(jd, set())
            for term, query in zip(terms, queries):
                best = max(range(len(chunks)), key=lambda i: cosine(query, vectors[i]))
                similarity = cosine(query, vectors[best])
                (covered if term.lower() in truth else uncovered).append(similarity)
                by_pair.append((name, jd, term, similarity, term.lower() in truth))

    def stats(label, values):
        print(f"  {label:10} n={len(values):3}  min={min(values):.3f}  p10={percentile(values, .1):.3f}  "
              f"median={percentile(values, .5):.3f}  p90={percentile(values, .9):.3f}  max={max(values):.3f}")

    print("\nBest-chunk cosine similarity per requirement:")
    stats("covered", covered)
    stats("uncovered", uncovered)
    suggestion = suggest_window(covered, uncovered)
    print(f"\nSuggested calibration:  LOW = {suggestion['LOW']}   HIGH = {suggestion['HIGH']}")
    print(f"Separation gap (covered p10 - uncovered p90): {suggestion['gap']}"
          + ("   << groups OVERLAP: consider a different query template" if suggestion["overlap"] else ""))
    print("\nPut LOW/HIGH into app/ats/semantic.py, then run the test suite.")
    print(f"Live embedding requests used: {used}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
