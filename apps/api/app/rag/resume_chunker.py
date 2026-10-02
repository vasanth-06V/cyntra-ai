"""Structure-aware, section-labelled resume chunking (v2).

What went wrong with v1 (rag/chunking.py): only 11 exact whole-line headings
were recognised ("PROFESSIONAL EXPERIENCE", "Work History & Projects" and
"Technical Skills & Tools" all slipped through), whole sections became single
blobs, long sections were cut mid-bullet by fixed 1,500-character windows, and
chunks carried no label.

v2 normalizes the extracted text (wrapped lines, bullet glyphs, hyphenation,
page furniture), finds sections by keyword in any case (with "&", colons and
inline content), splits experience into role blocks, splits long blocks on
bullet/sentence boundaries (never mid-line), merges tiny fragments, and
prefixes every chunk with "Section | role" so a chunk is meaningful on its own
when it is embedded or shown as evidence.
"""

import re
from dataclasses import dataclass

TARGET_CHARS = 900  # ~225 tokens: focused enough for a short query to match
MIN_CHARS = 120  # smaller fragments are merged into a neighbour

# canonical section -> keywords that identify a heading (first match wins)
_SECTION_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("experience", ("experience", "employment", "work history", "career history", "professional history")),
    ("projects", ("projects", "research", "publications")),
    ("skills", ("skills", "technologies", "tech stack", "tools", "languages", "frameworks", "competencies", "expertise")),
    ("education", ("education", "academic", "qualifications", "training")),
    ("certifications", ("certifications", "certificates", "licenses", "licences")),
    ("achievements", ("achievements", "awards", "honors", "honours", "accomplishments")),
    ("summary", ("summary", "profile", "objective", "about me", "about")),
    ("other", ("volunteer", "volunteering", "leadership", "interests", "activities", "references")),
]

_BULLET_GLYPHS = "•▪●◦‣∙·◾■□➢➤►–—*"
_MONTH = r"(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+)?"
_DATE_RANGE = re.compile(
    rf"{_MONTH}(?:19|20)\d{{2}}\s*(?:-|–|—|to)\s*{_MONTH}(?:(?:19|20)\d{{2}}|present|now|current|today)",
    re.IGNORECASE,
)
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")


@dataclass
class ResumeChunk:
    section: str
    content: str  # what is embedded: "Section | role\nbody"
    body: str  # the raw text slice (without the contextual header)
    title: str = ""  # role/company line when there is one


# --------------------------------------------------------------- normalizing


def _is_bullet(line: str) -> bool:
    return line.startswith("- ")


def normalize_resume_text(text: str) -> str:
    """Undo what PDF/DOCX extraction does to a resume."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace(" ", " ")
    text = re.sub(r"[​-‏⁠﻿]", "", text)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]

    # page headers/footers: short non-bullet lines repeated three or more times
    counts: dict[str, int] = {}
    for line in lines:
        if line and len(line) <= 60:
            counts[line] = counts.get(line, 0) + 1
    lines = [ln for ln in lines if not (ln and counts.get(ln, 0) >= 3)]

    out: list[str] = []
    for line in lines:
        if line and line[0] in _BULLET_GLYPHS and (len(line) == 1 or line[1] == " "):
            line = "- " + line[1:].strip()
        if out and line and out[-1] and _continues_previous(out[-1], line):
            prev = out[-1]
            if prev.endswith("-") and prev[-2:-1].isalpha():
                out[-1] = prev[:-1] + line  # "exper-" + "ience"
            else:
                out[-1] = f"{prev} {line}"
            continue
        out.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def _continues_previous(previous: str, line: str) -> bool:
    """A wrapped line: starts lowercase, the previous line was a full-width
    line that did not end a sentence, and this is not contact info (an email
    or URL also starts lowercase but is its own line)."""
    if not line[0].islower() or "@" in line or line.startswith(("http", "www.")):
        return False
    if len(previous) < 40 or _heading_of(previous) or previous.endswith((".", "!", "?", ":")):
        return False
    return True


# ------------------------------------------------------------------ sections


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z]+", text.lower())


def _match_section(label: str) -> str | None:
    cleaned = " ".join(_words(label))
    if not cleaned:
        return None
    for section, keywords in _SECTION_KEYWORDS:
        for keyword in keywords:
            if re.search(rf"\b{re.escape(keyword)}\b", cleaned):
                return section
    return None


def _heading_of(line: str) -> tuple[str, str, str] | None:
    """(section, label, inline_content) if `line` is a section heading: plain
    ("EXPERIENCE"), decorated ("Technical Skills & Tools:") or with content on
    the same line ("Languages & Frameworks: Python, Go")."""
    stripped = line.strip()
    if not stripped or _is_bullet(stripped) or len(stripped) > 90:
        return None

    inline = re.match(r"^([A-Za-z][A-Za-z &/,\-]{2,45}):\s*(.+)$", stripped)
    if inline and len(inline.group(1).split()) <= 5:
        section = _match_section(inline.group(1))
        if section:
            return section, inline.group(1).strip(), inline.group(2).strip()

    label = stripped.rstrip(":").strip()
    if label.endswith((".", ",", ";")) or len(label.split()) > 6 or _DATE_RANGE.search(label):
        return None
    section = _match_section(label)
    if section and (label.isupper() or label.istitle() or len(label.split()) <= 3 or label == label.lower()):
        return section, label, ""
    return None


@dataclass
class _Section:
    name: str
    lines: list[str]


def _split_sections(text: str) -> list[_Section]:
    sections: list[_Section] = [_Section("header", [])]
    for line in text.split("\n"):
        heading = _heading_of(line)
        if not heading:
            sections[-1].lines.append(line)
            continue
        name, label, inline = heading
        # consecutive headings of one kind (Languages: ..., Tools: ...) form one section
        if not (sections[-1].name == name and sections[-1].lines):
            sections.append(_Section(name, []))
        if inline:
            sections[-1].lines.append(f"{label}: {inline}")
    return [s for s in sections if "\n".join(s.lines).strip()]


# -------------------------------------------------------------------- blocks


def _is_role_line(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and not _is_bullet(stripped) and bool(_DATE_RANGE.search(stripped))


def _blocks(section: _Section) -> list[list[str]]:
    """Role blocks for experience/projects; paragraph blocks elsewhere."""
    if section.name in ("experience", "projects"):
        blocks: list[list[str]] = [[]]
        for line in section.lines:
            if _is_role_line(line) and any(b.strip() for b in blocks[-1]):
                blocks.append([])
            blocks[-1].append(line)
        return [[ln for ln in b if ln.strip()] for b in blocks if any(ln.strip() for ln in b)]

    blocks = [[]]
    for line in section.lines:
        if not line.strip():
            if blocks[-1]:
                blocks.append([])
            continue
        blocks[-1].append(line)
    return [b for b in blocks if b]


def _pieces(lines: list[str], limit: int) -> list[str]:
    """Splits one block on bullet boundaries (then sentences) -- never
    mid-line -- repeating the last bullet at the start of the next piece."""
    units: list[str] = []
    for line in lines:
        if len(line) > limit:
            units.extend(s for s in _SENTENCE_BREAK.split(line) if s.strip())
        else:
            units.append(line)

    pieces: list[list[str]] = [[]]
    size = 0
    for unit in units:
        if pieces[-1] and size + len(unit) + 1 > limit:
            carry = pieces[-1][-1] if _is_bullet(pieces[-1][-1]) else None
            pieces.append([carry] if carry else [])
            size = len(carry) if carry else 0
        pieces[-1].append(unit)
        size += len(unit) + 1
    return ["\n".join(p) for p in pieces if p]


def _skills_text(section: _Section) -> str:
    """A skills section as one tidy list: bullets/pipes flattened, a leading
    "Label:" kept as a group heading, duplicates dropped across groups."""
    seen: set[str] = set()
    groups: list[str] = []
    for line in section.lines:
        line = line.lstrip("- ").strip()
        if not line:
            continue
        label = ""
        match = re.match(r"^([A-Za-z][A-Za-z &/]{1,30}):\s*(.*)$", line)
        if match:
            label, line = match.group(1).strip(), match.group(2)
        items = []
        for item in re.split(r"\s*[,;|•·]\s*", line):
            key = item.strip().lower()
            if key and key not in seen:
                seen.add(key)
                items.append(item.strip())
        if items:
            groups.append(f"{label}: {', '.join(items)}" if label else ", ".join(items))
    return "; ".join(groups)


# ----------------------------------------------------------------- the chunker


def chunk_resume(text: str, target_chars: int = TARGET_CHARS) -> list[ResumeChunk]:
    """Section-labelled chunks for embedding and for showing evidence."""
    text = normalize_resume_text(text)
    if not text:
        return []

    chunks: list[ResumeChunk] = []
    for section in _split_sections(text):
        if section.name == "header":
            body = "\n".join(section.lines).strip()
            chunks.append(ResumeChunk("header", f"Header\n{body}", body))
            continue

        label = section.name
        if label == "skills":
            body = _skills_text(section)
            for piece in _pieces([body], target_chars * 2) if body else []:
                chunks.append(ResumeChunk("skills", f"Skills\n{piece}", piece))
            continue

        pending: list[tuple[str, str]] = []  # (title, body)
        for block in _blocks(section):
            is_role = label in ("experience", "projects") and _is_role_line(block[0])
            title = block[0].strip() if is_role else ""
            body = "\n".join(block[1:] if is_role else block).strip() or title
            pending.append((title, body))

        # fragments too small to stand alone join the previous block
        merged: list[tuple[str, str]] = []
        for title, body in pending:
            if merged and len(title) + len(body) < MIN_CHARS:
                prev_title, prev_body = merged[-1]
                extra = f"{title}\n{body}".strip() if title else body
                merged[-1] = (prev_title, f"{prev_body}\n{extra}".strip())
            else:
                merged.append((title, body))

        for title, body in merged:
            header = f"{label.capitalize()} | {title[:90]}" if title else label.capitalize()
            for piece in _pieces(body.split("\n"), target_chars):
                chunks.append(ResumeChunk(label, f"{header}\n{piece}", piece, title))

    return [c for c in chunks if c.body.strip()]
