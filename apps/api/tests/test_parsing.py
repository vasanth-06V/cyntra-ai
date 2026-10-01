import io

import pytest
from docx import Document

from app.rag.parsing import extract_text
from app.rag.parsing.docx import extract_text_from_docx


def _build_docx_bytes(paragraphs: list[str]) -> bytes:
    document = Document()
    for p in paragraphs:
        document.add_paragraph(p)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_extract_text_from_docx_round_trip():
    file_bytes = _build_docx_bytes(["Jane Doe", "Software Engineer", "jane@example.com"])
    text = extract_text_from_docx(file_bytes)
    assert "Jane Doe" in text
    assert "Software Engineer" in text
    assert "jane@example.com" in text


def test_extract_text_from_docx_skips_empty_paragraphs():
    file_bytes = _build_docx_bytes(["Line one", "", "   ", "Line two"])
    text = extract_text_from_docx(file_bytes)
    assert text == "Line one\nLine two"


def test_extract_text_dispatches_to_docx_by_extension():
    file_bytes = _build_docx_bytes(["Dispatch check"])
    text = extract_text("resume.DOCX", file_bytes)
    assert "Dispatch check" in text


def test_extract_text_raises_for_unsupported_extension():
    with pytest.raises(ValueError, match="Unsupported file type"):
        extract_text("resume.txt", b"plain text")
