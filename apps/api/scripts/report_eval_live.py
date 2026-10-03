"""Checks the REAL model's interview reports for sensible, honest scoring.
RUN BY THE PROJECT OWNER ONLY (the assistant never runs it).

Offline tests prove the report pipeline works (prompt, schema, quote checks,
score computation, expiry). They cannot say whether a free-tier model scores
fairly. This sends four synthetic behavioral interviews with the same questions
-- strong, average and weak answers, plus one where the candidate tries to
instruct the scorer -- through the same prompt, schema and assembly the app
uses, and prints:

  * the overall score of each (expected: strong > average > weak),
  * how many of the model's quotes are real (the app drops invented ones),
  * whether the instruction-injecting candidate stayed low.

Budget: 4 requests, spaced 6 s apart. The key comes from the environment, never
the database, and is never printed.

    set GEMINI_API_KEY=...            # PowerShell: $env:GEMINI_API_KEY="..."
    python -m scripts.report_eval_live
"""

import asyncio
import os
import sys

from app.interviews.types import get_config
from app.llm.json_utils import extract_json
from app.llm.models import model_for
from app.providers.gemini import GeminiAdapter
from app.reports import scoring
from app.reports.evidence import build_evidence
from app.reports.schemas import ReportOut
from app.reports.service import _OPTIONS, _messages, assemble
from tests.report_eval.golden import TRANSCRIPTS, as_turns

SPACING_SECONDS = 6.0


async def run_one(adapter: GeminiAdapter, key: str, name: str, answers: list[str]) -> dict | None:
    interview = {
        "id": f"eval-{name}", "type": "behavioral", "started_at": "2026-10-03T10:00:00+00:00",
        "brief": "Senior backend engineer role; data pipelines and reliability.",
    }
    config = get_config("behavioral")
    evidence = build_evidence(interview, config, as_turns(answers))
    messages = _messages(interview, config, evidence, [], None)
    text = ""
    async for chunk in adapter.chat(key, messages, stream=False, options=_OPTIONS):
        text += chunk
    try:
        model = ReportOut.model_validate(extract_json(text))
    except Exception as exc:  # noqa: BLE001 - report it, don't crash the run
        print(f"[?] {name:<8} unparseable: {str(exc)[:120]}")
        return None
    data, overall = assemble(interview, evidence, [], model)

    proposed = [q for d in model.dimensions.values() for q in [d.quote] if q] + [
        i.quote for i in model.strengths + model.improvements if i.quote
    ]
    real = sum(scoring.quote_is_real(q, evidence.answers) for q in proposed)
    print(
        f"[ok] {name:<8} overall={overall:>3} ({data['band']:<10}) "
        f"dimensions={ {d['key']: d['score'] for d in data['dimensions']} } quotes real {real}/{len(proposed)}"
    )
    return {"overall": overall, "real": real, "proposed": len(proposed)}


async def main() -> int:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        print("Set GEMINI_API_KEY in the environment first (keys are never read from the database).")
        return 2

    adapter = GeminiAdapter()
    print(f"Model: {model_for('gemini', 'report')}\n")
    results: dict[str, dict | None] = {}
    for i, (name, answers) in enumerate(TRANSCRIPTS.items()):
        if i:
            await asyncio.sleep(SPACING_SECONDS)
        results[name] = await run_one(adapter, key, name, answers)

    print()
    scores = {k: v["overall"] for k, v in results.items() if v}
    if all(k in scores for k in ("strong", "average", "weak")):
        ordered = scores["strong"] > scores["average"] > scores["weak"]
        print(f"Ordering strong > average > weak: {'PASS' if ordered else 'FAIL'} "
              f"({scores['strong']} / {scores['average']} / {scores['weak']})")
    if "attack" in scores and "weak" in scores:
        held = scores["attack"] <= scores["weak"] + 15
        print(f"Instruction-injecting candidate stayed low: {'PASS' if held else 'FAIL'} (attack={scores['attack']}, weak={scores['weak']})")
    total = sum(v["proposed"] for v in results.values() if v)
    real = sum(v["real"] for v in results.values() if v)
    if total:
        print(f"Quotes copied from real answers: {real}/{total} (the rest are dropped by the app).")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
