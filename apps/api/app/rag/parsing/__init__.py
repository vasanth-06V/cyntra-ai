from app.rag.parsing.docx import extract_text_from_docx
from app.rag.parsing.pdf import extract_text_from_pdf


def extract_text(filename: str, file_bytes: bytes) -> str:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return extract_text_from_pdf(file_bytes)
    if lower.endswith(".docx"):
        return extract_text_from_docx(file_bytes)
    raise ValueError(f"Unsupported file type: {filename}")
