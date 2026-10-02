"""The eval harness: runs a chunker + a semantic scorer over the golden set with
the fake embedder and reports structural quality metrics.

A *pipeline* is a pair (chunker, semantic_scorer):
  chunker(text) -> list[EvalChunk]
  scorer(requirements, index) -> float in [0, 1]
so the same metrics can compare the v1 pipeline with v2 while both exist.
"""

from dataclasses import dataclass
from statistics import mean

from app.ats.scorer import composite_score, formatting_score, keyword_score

from . import fake_embedder as fe
from .golden import EVIDENCE, EXPECTED_SECTIONS, JDS, RANKING, RESUMES


@dataclass
class EvalChunk:
    body: str  # the raw slice of the resume
    content: str  # what would actually be embedded (may carry a contextual header)
    section: str | None = None


class Index:
    """In-memory stand-in for resume_chunks + the match RPCs."""

    def __init__(self, chunks: list[EvalChunk], embed=fe.embed):
        self.chunks = chunks
        self.vectors = [embed(c.content) for c in chunks]

    def top(self, query_vec: list[float], k: int = 1) -> list[tuple[float, EvalChunk]]:
        scored = sorted(
            ((fe.cosine(query_vec, v), c) for v, c in zip(self.vectors, self.chunks)),
            key=lambda pair: pair[0],
            reverse=True,
        )
        return scored[:k]


# ------------------------------------------------------------------ pipelines


def v1_chunker(text: str) -> list[EvalChunk]:
    from app.rag.chunking import chunk_text

    return [EvalChunk(body=c, content=c, section=None) for c in chunk_text(text)]


def v1_semantic(requirements: dict, index: Index) -> float:
    """Mean of the best chunk's raw cosine per requirement (the original design)."""
    terms = requirements["must_have"] + requirements["nice_to_have"]
    sims = [max(0.0, (index.top(fe.embed(f"{t}"), 1) or [(0.0, None)])[0][0]) for t in terms]
    return sum(sims) / len(sims) if sims else 0.0


# ------------------------------------------------------------------ metrics


def chunk_stats(text: str, chunks: list[EvalChunk]) -> dict:
    """`cut_mid_line` counts body lines that are a proper fragment of a source
    line (a chunk boundary fell inside a line). Lines the normalizer joined
    (wrapped text) are longer than any source line, so they are not counted."""
    source_lines = [" ".join(ln.split()) for ln in text.splitlines() if ln.strip()]
    whole = set(source_lines)
    cuts = 0
    for chunk in chunks:
        for line in chunk.body.splitlines():
            line = " ".join(line.split())
            if len(line) >= 8 and line not in whole and any(line in src for src in source_lines):
                cuts += 1
    return {
        "count": len(chunks),
        "max_chars": max((len(c.body) for c in chunks), default=0),
        "mean_chars": round(mean(len(c.body) for c in chunks)) if chunks else 0,
        "cut_mid_line": cuts,
    }


def section_recall(name: str, chunks: list[EvalChunk]) -> float:
    """Share of the resume's real sections that the chunker recognised. A
    section counts as found if some chunk is labelled with it, or (for
    unlabelled chunkers) a chunk *begins* with it."""
    expected = EXPECTED_SECTIONS[name]
    found = 0
    for want in expected:
        for c in chunks:
            label = (c.section or c.body.strip().splitlines()[0]).lower()
            if want in label:
                found += 1
                break
    return found / len(expected)


def evidence_hit(name: str, jd: str, chunks: list[EvalChunk], k: int = 1) -> float:
    """For each requirement the resume genuinely covers: does one of the top-k
    chunks (by fake-embedding similarity) actually mention it?"""
    covered = EVIDENCE.get(name, {}).get(jd, set())
    if not covered:
        return 1.0
    index = Index(chunks)
    hits = 0
    for term in covered:
        for _, chunk in index.top(fe.embed(term), k):
            if term in chunk.content.lower():
                hits += 1
                break
    return hits / len(covered)


def semantic_scores(jd: str, chunker, scorer) -> dict[str, float]:
    requirements = JDS[jd]
    return {name: scorer(requirements, Index(chunker(text))) for name, text in RESUMES.items()}


def composite_scores(jd: str, chunker, scorer) -> dict[str, int]:
    requirements = JDS[jd]
    out = {}
    for name, text in RESUMES.items():
        semantic = scorer(requirements, Index(chunker(text)))
        out[name] = composite_score(keyword_score(requirements, text), semantic, formatting_score(text))
    return out


def ranking_quality(jd: str, scores: dict[str, float | int]) -> dict:
    groups = RANKING[jd]
    strong, middle, weak = (groups[g] for g in ("strong", "middle", "weak"))
    pairs = [(s, w) for s in strong for w in weak]
    correct = sum(1 for s, w in pairs if scores[s] > scores[w])
    margin = min(scores[s] for s in strong) - max(scores[w] for w in weak)
    ordered = all(min(scores[s] for s in strong) > max(scores[m] for m in middle) > max(scores[w] for w in weak) - 1e-9 for _ in [0])
    return {"pair_accuracy": correct / len(pairs), "margin": round(margin, 3), "strong>middle>weak": ordered}


def weak_resume_floor(jd: str, scores: dict[str, float | int]) -> float:
    """The best score an unrelated resume gets: lower is better (a resume with
    none of the skills should not look half-qualified)."""
    return max(scores[w] for w in RANKING[jd]["weak"])
