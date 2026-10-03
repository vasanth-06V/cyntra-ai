"""Loads the three starter coding problems (with reference solutions) into the
question bank. RUN BY THE PROJECT OWNER ONLY (the assistant never runs it).

Each question is embedded (so interviews can find it by topic) with the key in
GEMINI_API_KEY: 3 documents in ONE embedding request. Questions that are already
in the bank (same type and exact text) are skipped, so re-running is safe.
Dry run by default.

    set GEMINI_API_KEY=...            # PowerShell: $env:GEMINI_API_KEY="..."
    python -m scripts.load_starter_questions            # shows what would be added
    python -m scripts.load_starter_questions --apply    # adds them
"""

import argparse
import asyncio
import os
import sys

from app.db import questions as questions_repo
from app.interviews.question_bank import embedding_text
from app.llm.models import EMBEDDING_VERSION
from app.providers.gemini import GeminiAdapter
from tests.judge_eval.golden import PROBLEMS


async def main() -> int:
    parser = argparse.ArgumentParser(description="Load starter coding questions (owner-run).")
    parser.add_argument("--apply", action="store_true", help="actually insert (default: dry run)")
    args = parser.parse_args()

    existing = {(q["type"], q["question"]) for q in await questions_repo.list_questions(None, 500, 0)}
    todo = {k: p for k, p in PROBLEMS.items() if (p["type"], p["question"]) not in existing}
    print(f"{len(PROBLEMS) - len(todo)} already in the bank, {len(todo)} to add: {', '.join(todo) or '-'}")
    if not todo or not args.apply:
        print("(dry run: pass --apply to insert)" if todo else "Nothing to do.")
        return 0

    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        print("Set GEMINI_API_KEY in the environment first (keys are never read from the database).")
        return 2

    items = list(todo.values())
    vectors = await GeminiAdapter().embed_many(
        key, [embedding_text(p["type"], p["question"], p["topic"], p["tags"]) for p in items], kind="doc"
    )
    for problem, vector in zip(items, vectors):
        await questions_repo.insert_question(
            {
                "type": problem["type"],
                "question": problem["question"],
                "solution_code": problem["solution_code"],
                "solution_language": problem["solution_language"],
                "tags": problem["tags"],
                "topic": problem["topic"],
                "difficulty": problem["difficulty"],
                "embedding": vector,
                "embed_version": EMBEDDING_VERSION,
                "created_by": None,
            }
        )
        print(f"added: {problem['type']} / {problem['topic']} / difficulty {problem['difficulty']}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
