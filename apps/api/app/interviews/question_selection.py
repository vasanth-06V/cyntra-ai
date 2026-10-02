"""Choosing which bank questions an interview uses.

The first design took the top-N most similar questions to the whole JD, which
meant: near-duplicate questions together, the same questions on every run, the
same ones again for a user who already met them, and a query polluted by the
JD's boilerplate. Selection is now:

  1. candidates   nearest 12+ questions of the type, minus ones this user has
                  already been asked (a database function)
  2. diversify    maximal marginal relevance: each pick balances relevance to
                  the JD against similarity to what is already chosen, with a
                  penalty for repeating a topic
  3. vary         a little jitter, so two equally good questions don't always
                  resolve the same way

Pure functions: no database, no model, deterministic given the random source.
"""

import json
import math
import random
from collections.abc import Sequence

MMR_LAMBDA = 0.7  # 1.0 = pure relevance, 0.0 = pure diversity
SAME_TOPIC_PENALTY = 0.15
JITTER = 0.02


def _vector(raw) -> list[float]:
    if isinstance(raw, str):
        raw = json.loads(raw)
    return [float(x) for x in raw]


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def select_questions(
    candidates: list[dict],
    count: int,
    rng: random.Random | None = None,
    mmr_lambda: float = MMR_LAMBDA,
) -> list[dict]:
    """Picks `count` questions from `candidates` (rows of match_question_bank_v2:
    id, similarity, topic, embedding). Returns them most-relevant-first."""
    if count <= 0 or not candidates:
        return []
    rng = rng or random.Random()

    pool = [
        {**c, "_vec": _vector(c["embedding"]), "_score": float(c["similarity"]) + rng.uniform(0, JITTER)}
        for c in candidates
        if c.get("embedding") is not None
    ]
    selected: list[dict] = []
    while pool and len(selected) < count:
        best, best_value = None, -math.inf
        for item in pool:
            if selected:
                redundancy = max(_cosine(item["_vec"], s["_vec"]) for s in selected)
                same_topic = any(item.get("topic") and item.get("topic") == s.get("topic") for s in selected)
            else:
                redundancy, same_topic = 0.0, False
            value = mmr_lambda * item["_score"] - (1 - mmr_lambda) * redundancy - (SAME_TOPIC_PENALTY if same_topic else 0.0)
            if value > best_value:
                best, best_value = item, value
        pool.remove(best)
        selected.append(best)

    return [{k: v for k, v in s.items() if not k.startswith("_")} for s in selected]
