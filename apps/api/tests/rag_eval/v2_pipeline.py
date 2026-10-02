"""The v2 pipeline under evaluation: structure-aware chunker + calibrated,
keyword-aware semantic coverage (ats/semantic.py).

The fake embedder is far sharper than a real model, so the calibration window
here (FAKE_LOW/FAKE_HIGH) is specific to it; production constants come from
the owner-run live eval."""

from app.ats.scorer import term_present
from app.ats.semantic import build_coverage, query_text, semantic_score
from app.rag.resume_chunker import chunk_resume

from . import fake_embedder as fe
from .harness import EvalChunk, Index

FAKE_LOW = 0.10
FAKE_HIGH = 0.35


def chunker(text: str) -> list[EvalChunk]:
    return [EvalChunk(body=c.body, content=c.content, section=c.section) for c in chunk_resume(text)]


def coverage(requirements: dict, index: Index):
    terms = requirements["must_have"] + requirements["nice_to_have"]
    rows = []
    for i, term in enumerate(terms):
        similarity, best = index.top(fe.embed(query_text(term)), 1)[0]
        rows.append(
            {
                "q_idx": i,
                "similarity": similarity,
                "kw_hit": term_present(term, best.content),
                "kw_any": any(term_present(term, c.content) for c in index.chunks),
                "section": best.section,
                "content": best.content,
            }
        )
    return build_coverage(requirements, rows, low=FAKE_LOW, high=FAKE_HIGH)


def semantic(requirements: dict, index: Index) -> float:
    return semantic_score(coverage(requirements, index))
