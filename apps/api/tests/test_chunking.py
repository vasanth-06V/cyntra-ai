from app.rag.chunking import chunk_text


def test_empty_text_returns_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_short_text_returns_a_single_chunk():
    text = "Jane Doe\nSoftware Engineer\njane@example.com"
    chunks = chunk_text(text)
    assert chunks == [text]


def test_splits_on_known_section_headings():
    text = (
        "Jane Doe, Software Engineer\n\n"
        "Experience\n"
        "Built things at Acme Corp for 3 years.\n\n"
        "Education\n"
        "BS Computer Science, State University.\n\n"
        "Skills\n"
        "Python, TypeScript, SQL."
    )
    chunks = chunk_text(text, max_chars=1000)

    assert len(chunks) == 4  # preamble + 3 sections
    assert "Jane Doe" in chunks[0]
    assert chunks[1].startswith("Experience")
    assert chunks[2].startswith("Education")
    assert chunks[3].startswith("Skills")


def test_long_section_without_headings_falls_back_to_fixed_windows():
    text = "word " * 1000  # far longer than max_chars
    chunks = chunk_text(text, max_chars=200, overlap=20)

    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 200

    # Overlap means consecutive chunks share trailing/leading content.
    assert chunks[0][-20:] in chunks[1]


def test_long_section_with_headings_still_gets_fixed_windowed():
    long_experience = "did a thing. " * 200
    text = f"Experience\n{long_experience}"
    chunks = chunk_text(text, max_chars=300, overlap=30)

    assert len(chunks) > 1
    assert all(c.strip() for c in chunks)
