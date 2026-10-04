import io

import pdfplumber

_MAX_PAGES = 15  # a resume is a few pages; bounds the CPU a hostile PDF can burn


def extract_text_from_pdf(file_bytes: bytes) -> str:
    text_parts: list[str] = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages[:_MAX_PAGES]:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n\n".join(text_parts)
