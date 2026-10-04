"""Deterministic parts of a report: the overall score, the quote check and the
caps that keep the coding score consistent with the stored code review. The
model proposes 1-5 dimension scores; nothing it says can set the overall
number directly."""

import re

LABELS = {
    "communication": "Communication",
    "structure": "Structure and clarity",
    "technical_depth": "Technical depth",
    "role_relevance": "Relevance to the role",
    "coding_quality": "Coding quality",
}

# Weights per interview type (only dimensions that have a score count; the
# rest are re-normalised, so a missing coding score doesn't drag anything down).
_CODING = {"technical_depth": 0.30, "coding_quality": 0.25, "communication": 0.15, "structure": 0.15, "role_relevance": 0.15}
_TALKING = {"communication": 0.30, "structure": 0.25, "role_relevance": 0.25, "technical_depth": 0.20}
_TECHNICAL = {"technical_depth": 0.35, "structure": 0.25, "communication": 0.20, "role_relevance": 0.20}

WEIGHTS: dict[str, dict[str, float]] = {
    "coding": _CODING,
    "webd": _CODING,
    "sde": _CODING,
    "behavioral": _TALKING,
    "hr": _TALKING,
    "ml_ai": _TECHNICAL,
    "system_design": _TECHNICAL,
    "case_study": _TECHNICAL,
}

# The coding score may not exceed what the stored review of the code supports.
RESULT_CAP = {"correct": 5, "mostly_correct": 4, "incorrect": 2, "incomplete": 2}


def coding_cap(results: list[str]) -> int | None:
    """The strictest cap over the submitted problems, or None if no code was submitted."""
    caps = [RESULT_CAP.get(r, 3) for r in results]
    return min(caps) if caps else None


def apply_caps(dimensions: dict[str, int | None], code_results: list[str]) -> dict[str, int | None]:
    out = dict(dimensions)
    cap = coding_cap(code_results)
    if cap is None:
        out["coding_quality"] = None  # nothing was submitted: there is nothing to score
    elif out.get("coding_quality") is not None:
        out["coding_quality"] = min(out["coding_quality"], cap)
    else:
        # The model gave no coding score although code was reviewed: use the
        # review itself (never better than "adequate" without the model's say-so).
        out["coding_quality"] = min(cap, 3)
    return out


def overall_score(interview_type: str, scores: dict[str, int | None]) -> int:
    """0-100 from the weighted mean of the scored dimensions (1 -> 20, 5 -> 100)."""
    weights = WEIGHTS.get(interview_type, _TECHNICAL)
    used = [(weights.get(k, 0.0), s) for k, s in scores.items() if s is not None and weights.get(k, 0.0) > 0]
    total = sum(w for w, _ in used)
    if not total:
        return 0
    mean = sum(w * s for w, s in used) / total
    return round(mean * 20)


def band(score: int) -> str:
    if score >= 80:
        return "Strong"
    if score >= 60:
        return "Good"
    if score >= 40:
        return "Developing"
    return "Needs work"


_NON_WORD = re.compile(r"[^a-z0-9]+")


def _norm(text: str) -> str:
    return _NON_WORD.sub(" ", text.lower()).strip()


def quote_is_real(quote: str | None, answers: list[str], min_chars: int = 12) -> bool:
    """A quote counts only if it appears (ignoring case and punctuation) inside
    a single answer the candidate gave."""
    if not quote:
        return False
    needle = _norm(quote)
    if len(needle) < min_chars:
        return False
    return any(needle in _norm(a) for a in answers)
