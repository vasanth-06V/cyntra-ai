import pytest

from app.ats.scorer import composite_score, formatting_score, keyword_score, missing_terms


def _requirements(must_have=None, nice_to_have=None):
    return {"must_have": must_have or [], "nice_to_have": nice_to_have or []}


def test_keyword_score_full_match():
    requirements = _requirements(must_have=["Python", "SQL"], nice_to_have=["Docker"])
    resume = "Experienced with Python, SQL, and Docker."
    assert keyword_score(requirements, resume) == 1.0


def test_keyword_score_partial_match_weights_must_have_double():
    # 1 of 2 must-have matched (weight 2), 0 of 1 nice-to-have (weight 1).
    # matched = 2, total = 2*2 + 1 = 5 -> 0.4
    requirements = _requirements(must_have=["Python", "Rust"], nice_to_have=["Docker"])
    resume = "Experienced with Python only."
    assert keyword_score(requirements, resume) == pytest.approx(2 / 5)


def test_keyword_score_matches_via_synonym():
    requirements = _requirements(must_have=["JavaScript"])
    resume = "5 years of JS experience."
    assert keyword_score(requirements, resume) == 1.0


def test_keyword_score_no_requirements_is_perfect():
    assert keyword_score(_requirements(), "anything") == 1.0


def test_missing_terms_reports_unmatched():
    requirements = _requirements(must_have=["Python", "Rust"], nice_to_have=["Docker", "AWS"])
    resume = "Python and Docker experience."
    missing_must, missing_nice = missing_terms(requirements, resume)
    assert missing_must == ["Rust"]
    assert missing_nice == ["AWS"]


def test_formatting_score_rewards_contact_info_and_sections():
    resume = (
        "Jane Doe\njane@example.com\n+1 555-123-4567\n\n"
        "Experience\nBuilt things for 3 years at a normal company with real sentences.\n\n"
        "Education\nState University, long enough lines to not look fragmented."
    )
    assert formatting_score(resume) == 1.0


def test_formatting_score_penalizes_missing_everything():
    assert formatting_score("ab\ncd\nef") < 1.0


def test_formatting_score_empty_text_is_zero():
    assert formatting_score("") == 0.0
    assert formatting_score("   ") == 0.0


def test_composite_score_weights_40_40_20():
    # 1.0 keyword, 0.5 semantic, 0.0 formatting -> 0.4*1 + 0.4*0.5 + 0.2*0 = 0.6 -> 60
    assert composite_score(1.0, 0.5, 0.0) == 60
