"""A deterministic stand-in for the embedding model, so the *pipeline* (chunking,
section labels, retrieval, score calibration, ranking) can be evaluated offline.

It is a hashed bag-of-words: every word maps to a fixed pseudo-random unit
vector, a text is the normalized sum of its words' vectors (stop words
dropped, a few skill synonyms folded together). Texts that share vocabulary are
similar; texts that don't are near-orthogonal. That is much *sharper* than a
real model, so absolute similarity values from here must never be used to set
calibration constants -- only the owner-run live eval (scripts/rag_eval_live.py)
does that. What this gives us is a fast, reproducible signal for structural
regressions.
"""

import hashlib
import math
import random
import re

DIMENSIONS = 768

_STOP = {
    "a", "an", "and", "the", "of", "in", "on", "at", "to", "for", "with", "by", "as", "is", "was", "are",
    "from", "that", "this", "it", "its", "or", "be", "been", "were", "per", "than", "into", "over",
}
_FOLD = {
    "postgres": "postgresql", "psql": "postgresql", "k8s": "kubernetes", "eks": "kubernetes",
    "containerised": "docker", "containerized": "docker", "js": "javascript", "ts": "typescript",
    "reactjs": "react", "css3": "css", "tailwind": "css", "ml": "machinelearning",
}
_WORD = re.compile(r"[a-z0-9+#.]+")


def tokens(text: str) -> list[str]:
    out = []
    for word in _WORD.findall(text.lower()):
        word = word.strip(".")
        if not word or word in _STOP or len(word) < 2:
            continue
        out.append(_FOLD.get(word, word))
    return out


def _word_vector(word: str) -> list[float]:
    seed = int.from_bytes(hashlib.sha256(word.encode()).digest()[:8], "big")
    rng = random.Random(seed)
    return [rng.gauss(0, 1) for _ in range(DIMENSIONS)]


_cache: dict[str, list[float]] = {}


def embed(text: str) -> list[float]:
    words = tokens(text)
    total = [0.0] * DIMENSIONS
    for word in words:
        vec = _cache.get(word) or _cache.setdefault(word, _word_vector(word))
        for i, x in enumerate(vec):
            total[i] += x
    norm = math.sqrt(sum(x * x for x in total))
    return [x / norm for x in total] if norm else total


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))
