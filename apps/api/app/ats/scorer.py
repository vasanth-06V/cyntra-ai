import re

# A small, curated synonym map for common abbreviations -- real ATS keyword
# matching needs to catch "JS" vs "JavaScript", not just exact substrings.
# Extend this list as gaps are found; it's intentionally not exhaustive.
SYNONYMS: dict[str, list[str]] = {
    "javascript": ["js"],
    "typescript": ["ts"],
    "python": ["py"],
    "machine learning": ["ml"],
    "artificial intelligence": ["ai"],
    "kubernetes": ["k8s"],
    "continuous integration": ["ci"],
    "continuous deployment": ["cd"],
    "user interface": ["ui"],
    "user experience": ["ux"],
    "application programming interface": ["api"],
    "database": ["db"],
    "natural language processing": ["nlp"],
}


def _synonym_group(term: str) -> list[str]:
    term_lower = term.lower()
    for canonical, synonyms in SYNONYMS.items():
        group = [canonical, *synonyms]
        if term_lower in group:
            return group
    return [term_lower]


def _contains_word(variant: str, text: str) -> bool:
    # Whole-word match: plain substring search made "ml" match "HTML", "ci"
    # match "specific" and "java" match "JavaScript". The lookarounds (instead
    # of \b) keep terms like "c++", "c#" and ".net" working.
    return re.search(rf"(?<![a-z0-9]){re.escape(variant)}(?![a-z0-9])", text) is not None


def _term_present(term: str, resume_lower: str) -> bool:
    return any(_contains_word(variant, resume_lower) for variant in _synonym_group(term))


def keyword_score(requirements: dict, resume_text: str) -> float:
    """Weighted exact+synonym match: must-have terms count double a
    nice-to-have, since missing a required skill matters more."""
    must_have = requirements.get("must_have", [])
    nice_to_have = requirements.get("nice_to_have", [])
    total_weight = len(must_have) * 2 + len(nice_to_have)
    if total_weight == 0:
        return 1.0

    resume_lower = resume_text.lower()
    matched = sum(2 for t in must_have if _term_present(t, resume_lower))
    matched += sum(1 for t in nice_to_have if _term_present(t, resume_lower))
    return matched / total_weight


def missing_terms(requirements: dict, resume_text: str) -> tuple[list[str], list[str]]:
    resume_lower = resume_text.lower()
    missing_must = [t for t in requirements.get("must_have", []) if not _term_present(t, resume_lower)]
    missing_nice = [t for t in requirements.get("nice_to_have", []) if not _term_present(t, resume_lower)]
    return missing_must, missing_nice


_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"(\+?\d[\d\-\s()]{7,}\d)")
_SECTION_RE = re.compile(r"\b(experience|education|skills)\b", re.IGNORECASE)


def formatting_score(resume_text: str) -> float:
    """Heuristic proxy for "would a real ATS parser read this cleanly":
    checks for contact info, standard section headers, and average line
    length (a badly-extracted multi-column PDF tends to produce lots of
    very short fragment lines)."""
    if not resume_text.strip():
        return 0.0

    checks_passed = 0
    total_checks = 4

    if _EMAIL_RE.search(resume_text):
        checks_passed += 1
    if _PHONE_RE.search(resume_text):
        checks_passed += 1
    if _SECTION_RE.search(resume_text):
        checks_passed += 1

    lines = [line for line in resume_text.splitlines() if line.strip()]
    if lines:
        avg_len = sum(len(line) for line in lines) / len(lines)
        if avg_len >= 20:
            checks_passed += 1

    return checks_passed / total_checks


def composite_score(keyword: float, semantic: float, formatting: float) -> int:
    """Weighted per the plan: 40% keyword, 40% semantic, 20% formatting."""
    return round((0.4 * keyword + 0.4 * semantic + 0.2 * formatting) * 100)
