"""ATS semantic coverage: for each JD requirement, how well does the resume
actually back it up?

The first design averaged the raw cosine similarity of each requirement's best
chunk. Raw cosines from an embedding model sit in a narrow band (a resume
with none of the skills still lands around 0.5), so the score barely moved and
40% of the composite was noise. Instead:

  * each requirement is scored 0..1 by mapping its best similarity through a
    calibrated window [LOW, HIGH] (LOW = what an unrelated chunk scores,
    HIGH = what a clearly relevant one scores);
  * an exact keyword in the best chunk with at least a weak similarity counts
    as full coverage, and a keyword anywhere in the resume sets a floor
    (embeddings are poor at short exact tokens like "C#", "k8s", ".NET");
  * must-haves weigh twice a nice-to-have, matching the keyword score;
  * the best chunk and its section are kept as evidence for the feedback.

LOW / HIGH are placeholders until the owner runs `python -m scripts.rag_eval_live`
against the real embedding model and pastes the suggested values in.
"""

from dataclasses import dataclass

# Calibration window for gemini-embedding-001 (RETRIEVAL_QUERY vs RETRIEVAL_DOCUMENT).
# PLACEHOLDERS -- set from the live eval output.
LOW = 0.55
HIGH = 0.80

KW_SIM_MIN = 0.50  # a keyword hit only counts as full coverage if the chunk is at least this similar
KW_ANYWHERE_FLOOR = 0.70  # keyword present somewhere in the resume: at least this covered
COVERED_AT = 0.50  # coverage at or above this = "the resume supports this requirement"

WEIGHT = {"must": 2.0, "nice": 1.0}


@dataclass
class Coverage:
    term: str
    kind: str  # "must" | "nice"
    strength: float  # 0..1
    similarity: float
    keyword_in_chunk: bool
    keyword_anywhere: bool
    section: str | None
    evidence: str  # the best chunk, trimmed

    @property
    def covered(self) -> bool:
        return self.strength >= COVERED_AT


def query_text(term: str) -> str:
    """Bare skill names embed poorly against paragraphs; a short sentence
    frame puts the query in the same register as the resume text."""
    return f"Experience with {term}"


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def requirement_strength(
    similarity: float,
    keyword_in_chunk: bool,
    keyword_anywhere: bool,
    low: float = LOW,
    high: float = HIGH,
) -> float:
    strength = _clamp((similarity - low) / (high - low)) if high > low else 0.0
    if keyword_in_chunk and similarity >= KW_SIM_MIN:
        strength = 1.0
    elif keyword_anywhere:
        strength = max(strength, KW_ANYWHERE_FLOOR)
    return strength


def build_coverage(
    requirements: dict,
    matches: list[dict],
    low: float = LOW,
    high: float = HIGH,
) -> list[Coverage]:
    """`matches` are the rows of match_resume_chunks_multi: q_idx indexes the
    list must_have + nice_to_have."""
    terms = [(t, "must") for t in requirements["must_have"]] + [
        (t, "nice") for t in requirements["nice_to_have"]
    ]
    best: dict[int, dict] = {}
    for row in matches:
        idx = row["q_idx"]
        if idx not in best or row["similarity"] > best[idx]["similarity"]:
            best[idx] = row

    out: list[Coverage] = []
    for i, (term, kind) in enumerate(terms):
        row = best.get(i)
        if row is None:  # a resume with no chunks at all
            out.append(Coverage(term, kind, 0.0, 0.0, False, False, None, ""))
            continue
        similarity = max(0.0, float(row["similarity"]))
        out.append(
            Coverage(
                term=term,
                kind=kind,
                strength=requirement_strength(
                    similarity, bool(row["kw_hit"]), bool(row["kw_any"]), low, high
                ),
                similarity=round(similarity, 3),
                keyword_in_chunk=bool(row["kw_hit"]),
                keyword_anywhere=bool(row["kw_any"]),
                section=row.get("section"),
                evidence=(row.get("content") or "")[:240],
            )
        )
    return out


def semantic_score(coverage: list[Coverage]) -> float:
    total = sum(WEIGHT[c.kind] for c in coverage)
    if not total:
        return 0.0
    return sum(WEIGHT[c.kind] * c.strength for c in coverage) / total
