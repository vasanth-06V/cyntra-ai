import io
import re

import pdfplumber

_MAX_PAGES = 15  # a resume is a few pages; bounds the CPU a hostile PDF can burn

# pdfplumber's default (3) glues words together when a PDF sets its spaces
# tightly, as LaTeX resume templates do ("BachelorofTechnologyinComputerScience").
# That breaks keyword matching and gives the embeddings nonsense to work with.
# 1.5 splits those words and, checked against a real LaTeX resume, does not
# split ordinary words apart.
_X_TOLERANCE = 1.5

# Icon glyphs (phone, mail, LinkedIn...) come out as "(cid:131)" placeholders.
_CID_RE = re.compile(r"\(cid:\d+\)")


def extract_text_from_pdf(file_bytes: bytes) -> str:
    text_parts: list[str] = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages[:_MAX_PAGES]:
            page_text = page.extract_text(x_tolerance=_X_TOLERANCE)
            if page_text:
                text_parts.append(_CID_RE.sub("", page_text))
    return "\n\n".join(text_parts)
