import re

SECTION_HEADINGS = [
    "summary",
    "objective",
    "experience",
    "work experience",
    "employment history",
    "education",
    "skills",
    "technical skills",
    "projects",
    "certifications",
    "achievements",
]

_HEADING_PATTERN = re.compile(
    rf"^\s*({'|'.join(re.escape(h) for h in SECTION_HEADINGS)})\s*:?\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def chunk_text(text: str, max_chars: int = 1500, overlap: int = 200) -> list[str]:
    """Splits on common resume section headings when detectable (so a chunk
    stays within one semantic section like "Experience" or "Skills"),
    falling back to fixed-size windows with overlap for sections -- or whole
    documents -- too large or too unstructured to split that way."""
    text = text.strip()
    if not text:
        return []

    chunks: list[str] = []
    for section in _split_by_headings(text):
        chunks.extend(_fixed_window_chunks(section, max_chars, overlap))
    return [c for c in chunks if c.strip()]


def _split_by_headings(text: str) -> list[str]:
    matches = list(_HEADING_PATTERN.finditer(text))
    if not matches:
        return [text]

    sections = []
    if matches[0].start() > 0:
        # Preamble before the first heading (e.g. name/contact info).
        sections.append(text[: matches[0].start()])

    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append(text[m.start() : end])

    return sections


def _fixed_window_chunks(text: str, max_chars: int, overlap: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = end - overlap
    return chunks
