import pytest

from app.rag.resume_chunker import (
    MIN_CHARS,
    TARGET_CHARS,
    _heading_of,
    chunk_resume,
    normalize_resume_text,
)

# --- headings -----------------------------------------------------------------


@pytest.mark.parametrize(
    "line,section",
    [
        ("EXPERIENCE", "experience"),
        ("Professional Experience", "experience"),
        ("WORK EXPERIENCE & PROJECTS", "experience"),
        ("Employment History:", "experience"),
        ("Work History & Projects", "experience"),
        ("Technical Skills & Tools", "skills"),
        ("SKILLS", "skills"),
        ("Core Competencies", "skills"),
        ("Education", "education"),
        ("ACADEMIC BACKGROUND", "education"),
        ("Certifications & Licenses", "certifications"),
        ("Awards and Honors", "achievements"),
        ("Professional Summary", "summary"),
        ("Projects", "projects"),
        ("Volunteer Work", "other"),
    ],
)
def test_heading_variants_are_recognised(line, section):
    assert _heading_of(line)[0] == section


def test_inline_headings_carry_their_content():
    section, label, inline = _heading_of("Languages & Frameworks:  Python, TypeScript, React")
    assert (section, label, inline) == ("skills", "Languages & Frameworks", "Python, TypeScript, React")
    assert _heading_of("Education: BSc Software Engineering, 2018")[0] == "education"


@pytest.mark.parametrize(
    "line",
    [
        "Led a research team of five engineers.",  # a sentence, not a heading
        "Education Technology Lead, Acme (2020 - Present)",  # a role line with dates
        "- Skills development program for new hires",  # a bullet
        "Built tools used by the experience design team and shipped them to production in 2020",  # too long
        "",
    ],
)
def test_ordinary_lines_are_not_headings(line):
    assert _heading_of(line) is None


# --- normalization --------------------------------------------------------------


def test_bullet_glyphs_become_dashes_and_wrapped_lines_are_rejoined():
    raw = (
        "Experience\n"
        "• Designed and built a distributed event pipeline that processes millions of\n"
        "events per day across several regions.\n"
        "▪ Led the on-call rotation."
    )
    text = normalize_resume_text(raw)
    assert "- Designed and built a distributed event pipeline that processes millions of events per day" in text
    assert "- Led the on-call rotation." in text


def test_hyphenated_words_split_across_lines_are_rejoined():
    raw = "- Responsible for the migration of the legacy infra-\nstructure to a cloud-native platform."
    assert "infrastructure to a cloud-native" in normalize_resume_text(raw)


def test_contact_lines_are_never_glued_onto_the_line_above():
    text = normalize_resume_text("Priya Natarajan Marketing Manager at a very large company\npriya.n@example.com")
    assert text.splitlines() == ["Priya Natarajan Marketing Manager at a very large company", "priya.n@example.com"]


def test_repeated_page_furniture_is_dropped():
    raw = "Jane Doe - Resume\nExperience\n- Did things.\nJane Doe - Resume\n- More things.\nJane Doe - Resume\n"
    assert "Jane Doe - Resume" not in normalize_resume_text(raw)


# --- structure -------------------------------------------------------------------


def _roles_resume(bullets_per_role=3):
    def role(title, n):
        return f"{title}\n" + "\n".join(f"- Delivered result number {i} with measurable impact on the platform." for i in range(n))

    return "Jane Doe\njane@example.com\n\nExperience\n" + "\n\n".join(
        [role("Staff Engineer, Acme (2020 - Present)", bullets_per_role), role("Engineer, Initech (2016 - 2020)", bullets_per_role)]
    ) + "\n\nSkills\nPython, Go"


def test_each_role_is_its_own_chunk_with_a_contextual_header():
    chunks = chunk_resume(_roles_resume())
    experience = [c for c in chunks if c.section == "experience"]
    assert [c.title for c in experience] == ["Staff Engineer, Acme (2020 - Present)", "Engineer, Initech (2016 - 2020)"]
    assert experience[0].content.startswith("Experience | Staff Engineer, Acme (2020 - Present)\n")
    assert "Staff Engineer" not in experience[0].body  # body is the raw slice; the title lives in the header


def test_a_long_role_splits_on_bullets_never_mid_line_and_repeats_a_bullet_for_context():
    chunks = [c for c in chunk_resume(_roles_resume(bullets_per_role=40)) if c.section == "experience"]
    assert len(chunks) > 2
    for chunk in chunks:
        assert len(chunk.body) <= TARGET_CHARS * 1.3
        assert all(line.startswith("- ") for line in chunk.body.splitlines())  # every line is a whole bullet
    first, second = chunks[0].body.splitlines(), chunks[1].body.splitlines()
    assert first[-1] == second[0]  # one bullet of overlap


def test_tiny_fragments_are_merged_into_the_previous_block():
    text = "Experience\nSenior Dev, BigCo (2019 - Present)\n" + "\n".join(
        f"- Shipped feature {i} used by thousands of customers every day without incident." for i in range(4)
    ) + "\nIntern, Local Bank (2018 - 2019)\n- Wrote scripts."
    chunks = [c for c in chunk_resume(text) if c.section == "experience"]
    assert len(chunks) == 1 and "Wrote scripts." in chunks[0].body
    assert all(len(c.body) >= MIN_CHARS for c in chunks)


def test_skills_become_one_tidy_deduplicated_list():
    resume = "Skills\n- Python, Go\n- go, Docker | Kubernetes\nTools: Git, Python"
    chunks = [c for c in chunk_resume(resume) if c.section == "skills"]
    assert len(chunks) == 1
    body = chunks[0].body
    assert body == "Python, Go; Docker, Kubernetes; Tools: Git"  # duplicates gone, one group per source line, label kept


def test_text_without_any_headings_still_chunks_instead_of_failing():
    chunks = chunk_resume("Just a paragraph about a developer. " * 80)
    assert chunks and all(c.section == "header" or c.body for c in chunks)


def test_empty_input_gives_no_chunks():
    assert chunk_resume("") == [] and chunk_resume("  \n \n") == []


def test_a_wall_of_prose_is_split_at_sentence_boundaries():
    prose = "Experience\n" + " ".join(f"I did task number {i} and it went very well for everyone involved." for i in range(60))
    chunks = chunk_resume(prose)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.body) <= TARGET_CHARS * 1.3
        assert chunk.body.rstrip().endswith(".")


# --- eval gates on the golden set ----------------------------------------------------


def test_the_golden_resumes_meet_the_v2_quality_gates():
    from tests.rag_eval import harness as h
    from tests.rag_eval import v2_pipeline
    from tests.rag_eval.golden import RESUMES

    for name, text in RESUMES.items():
        chunks = v2_pipeline.chunker(text)
        stats = h.chunk_stats(text, chunks)
        jd = "frontend" if name == "frontend_dev" else "backend"
        assert h.section_recall(name, chunks) == 1.0, name
        assert stats["cut_mid_line"] == 0, name
        assert stats["max_chars"] <= TARGET_CHARS * 1.3, name
        assert h.evidence_hit(name, jd, chunks, k=1) == 1.0, name
        assert all(c.section for c in chunks)


def test_v1_is_documented_as_weak_where_v2_was_built_to_improve():
    from tests.rag_eval import harness as h
    from tests.rag_eval.golden import RESUMES

    caps = h.v1_chunker(RESUMES["caps_style"])
    messy = h.v1_chunker(RESUMES["messy_layout"])
    assert h.section_recall("caps_style", caps) < 1.0  # ALL-CAPS and "& Tools" headings missed
    assert len(messy) == 1  # the whole messy resume is one blob
