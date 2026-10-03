"""Measures how often the REAL model's code review agrees with the truth.
RUN BY THE PROJECT OWNER ONLY (the assistant never runs it).

Offline tests prove the review pipeline works (prompt, schema, storage, leak
filter); they cannot say whether the model judges code well. This sends the 12
labelled solutions in tests/judge_eval/golden.py (6 correct, 6 wrong, in Python,
JavaScript, TypeScript and C++) through the same prompt and schema the app uses,
and prints, per case, what the model said against the label, plus the overall
agreement.

Budget: 12 requests, spaced 5 s apart (about a minute). The key comes from the
environment, never the database, and is never printed.

    set GEMINI_API_KEY=...            # PowerShell: $env:GEMINI_API_KEY="..."
    python -m scripts.judge_eval_live            # Gemini (the app's default model)
    python -m scripts.judge_eval_live --only us_wrong_no_max   # one case
"""

import argparse
import asyncio
import os
import sys

from app.coding.schemas import ReviewOut
from app.coding.service import _REVIEW_OPTIONS, _review_messages
from app.interviews.types import get_config
from app.llm.json_utils import extract_json
from app.llm.models import model_for
from app.providers.gemini import GeminiAdapter
from tests.judge_eval.golden import CASES, PROBLEMS

SPACING_SECONDS = 5.0
RIGHT = {"correct", "mostly_correct"}
WRONG = {"incorrect", "incomplete"}


async def review(adapter: GeminiAdapter, key: str, case: dict) -> tuple[ReviewOut | None, str]:
    problem = PROBLEMS[case["problem"]]
    messages = _review_messages(
        {"brief": ""},
        get_config(problem["type"]),
        "problem_1",
        problem["question"],
        problem["solution_code"],
        problem["solution_language"],
        case["language"],
        case["code"],
        [],
    )
    text = ""
    async for chunk in adapter.chat(key, messages, stream=False, options=_REVIEW_OPTIONS):
        text += chunk
    try:
        return ReviewOut.model_validate(extract_json(text)), text
    except Exception as exc:  # noqa: BLE001 - report, don't crash the run
        return None, f"unparseable: {exc}"


async def main() -> int:
    parser = argparse.ArgumentParser(description="Live accuracy check of the code reviewer (owner-run).")
    parser.add_argument("--only", help="run a single case id")
    args = parser.parse_args()

    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        print("Set GEMINI_API_KEY in the environment first (keys are never read from the database).")
        return 2

    cases = [c for c in CASES if not args.only or c["id"] == args.only]
    if not cases:
        print("No such case id.")
        return 2

    adapter = GeminiAdapter()
    print(f"Model: {model_for('gemini', 'judge')}   cases: {len(cases)}\n")
    agree = unparsed = 0
    for i, case in enumerate(cases):
        if i:
            await asyncio.sleep(SPACING_SECONDS)
        out, raw = await review(adapter, key, case)
        if out is None:
            unparsed += 1
            print(f"[?] {case['id']:<28} label={case['expected']:<8} model: {raw[:90]}")
            continue
        ok = out.result in (RIGHT if case["expected"] == "correct" else WRONG)
        agree += ok
        mark = "OK " if ok else "BAD"
        print(
            f"[{mark}] {case['id']:<28} label={case['expected']:<8} model={out.result:<15} "
            f"approach={out.approach:<19} confidence={out.confidence}"
        )
        if not ok:
            print(f"       note: {case['note']}\n       trace: {out.trace[:200]}")

    judged = len(cases) - unparsed
    print(f"\nAgreement: {agree}/{judged} judged ({unparsed} unparseable) of {len(cases)} cases.")
    print("Wrong-but-labelled-correct (false alarms) and right-but-labelled-wrong (missed bugs) are the cases to read above.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
