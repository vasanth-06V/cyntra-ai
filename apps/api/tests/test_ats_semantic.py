import pytest

from app.ats import semantic
from app.ats.semantic import (
    COVERED_AT,
    HIGH,
    KW_ANYWHERE_FLOOR,
    LOW,
    build_coverage,
    query_text,
    requirement_strength,
    semantic_score,
)

REQ = {"must_have": ["Python", "Kubernetes"], "nice_to_have": ["Redis"], "experience_level": "mid", "title": "Eng"}


def row(i, sim, kw_hit=False, kw_any=False, section="experience", content="chunk text"):
    return {"q_idx": i, "similarity": sim, "kw_hit": kw_hit, "kw_any": kw_any, "section": section, "content": content}


# --- strength ------------------------------------------------------------------


def test_similarity_is_mapped_through_the_calibration_window():
    assert requirement_strength(LOW, False, False) == 0.0
    assert requirement_strength(HIGH, False, False) == 1.0
    assert requirement_strength((LOW + HIGH) / 2, False, False) == pytest.approx(0.5)
    assert requirement_strength(0.1, False, False) == 0.0  # below the window clamps to zero
    assert requirement_strength(0.99, False, False) == 1.0  # above clamps to one


def test_a_resume_with_no_relevant_content_scores_zero_not_half():
    """The original design gave ~0.5 for a resume with none of the skills."""
    unrelated_similarity = LOW - 0.02
    assert requirement_strength(unrelated_similarity, False, False) == 0.0


def test_an_exact_keyword_in_the_best_chunk_is_full_coverage_even_when_similarity_is_modest():
    assert requirement_strength(0.52, keyword_in_chunk=True, keyword_anywhere=True) == 1.0


def test_a_keyword_hit_in_a_chunk_that_is_not_similar_at_all_does_not_auto_cover():
    # the best chunk by similarity is irrelevant, but the term exists elsewhere -> only the floor
    assert requirement_strength(0.2, keyword_in_chunk=True, keyword_anywhere=True) == KW_ANYWHERE_FLOOR


def test_a_keyword_elsewhere_sets_a_floor_but_never_lowers_a_better_semantic_score():
    assert requirement_strength(0.3, False, True) == KW_ANYWHERE_FLOOR
    assert requirement_strength(HIGH, False, True) == 1.0


def test_the_floor_clears_the_covered_threshold():
    assert KW_ANYWHERE_FLOOR >= COVERED_AT


# --- coverage + score --------------------------------------------------------------------


def test_coverage_follows_requirement_order_and_keeps_the_evidence():
    rows = [row(0, 0.9, kw_hit=True, kw_any=True, content="Python services"), row(1, 0.3), row(2, 0.82)]
    coverage = build_coverage(REQ, rows)
    assert [c.term for c in coverage] == ["Python", "Kubernetes", "Redis"]
    assert [c.kind for c in coverage] == ["must", "must", "nice"]
    assert coverage[0].strength == 1.0 and coverage[0].evidence == "Python services" and coverage[0].section == "experience"
    assert coverage[1].strength == 0.0 and not coverage[1].covered
    assert coverage[2].covered


def test_the_best_row_wins_when_several_chunks_come_back_for_one_requirement():
    coverage = build_coverage(REQ, [row(0, 0.4, content="weak"), row(0, 0.85, content="strong"), row(1, 0.1), row(2, 0.1)])
    assert coverage[0].evidence == "strong"


def test_a_resume_with_no_chunks_covers_nothing():
    coverage = build_coverage(REQ, [])
    assert [c.strength for c in coverage] == [0.0, 0.0, 0.0]
    assert semantic_score(coverage) == 0.0


def test_must_haves_weigh_double_a_nice_to_have():
    all_must_covered = build_coverage(REQ, [row(0, 0.9, True, True), row(1, 0.9, True, True), row(2, 0.1)])
    only_nice_covered = build_coverage(REQ, [row(0, 0.1), row(1, 0.1), row(2, 0.9, True, True)])
    assert semantic_score(all_must_covered) == pytest.approx(4 / 5)
    assert semantic_score(only_nice_covered) == pytest.approx(1 / 5)


def test_semantic_score_of_nothing_is_zero():
    assert semantic_score([]) == 0.0


def test_the_query_is_a_sentence_not_a_bare_word():
    assert query_text("Kubernetes") == "Experience with Kubernetes"
    assert semantic.LOW < semantic.HIGH


# --- eval gates (fake embedder: pipeline structure, not model quality) ---------------------


def _scores(jd, chunker, scorer):
    from tests.rag_eval import harness as h

    return h.composite_scores(jd, chunker, scorer)


def test_v2_ranks_every_golden_pair_correctly_and_separates_far_better_than_v1():
    from tests.rag_eval import harness as h
    from tests.rag_eval import v2_pipeline

    for jd in ("backend", "frontend"):
        v1 = _scores(jd, h.v1_chunker, h.v1_semantic)
        v2 = _scores(jd, v2_pipeline.chunker, v2_pipeline.semantic)
        quality = h.ranking_quality(jd, v2)
        assert quality["pair_accuracy"] == 1.0 and quality["strong>middle>weak"], (jd, quality)
        assert quality["margin"] > h.ranking_quality(jd, v1)["margin"], jd
        assert h.weak_resume_floor(jd, v2) <= h.weak_resume_floor(jd, v1), jd
        assert h.weak_resume_floor(jd, v2) <= 25, jd  # a resume with none of the skills is not "half qualified"


def test_strong_resumes_score_high_and_the_unrelated_one_scores_only_its_formatting_points():
    from tests.rag_eval import v2_pipeline

    backend = _scores("backend", v2_pipeline.chunker, v2_pipeline.semantic)
    assert backend["strong_backend"] >= 85 and backend["caps_style"] >= 75
    assert backend["weak_unrelated"] <= 25


def test_adding_a_missing_skill_to_a_resume_never_lowers_and_here_raises_its_coverage():
    from tests.rag_eval import fake_embedder as fe  # noqa: F401
    from tests.rag_eval import v2_pipeline
    from tests.rag_eval.golden import JDS, RESUMES
    from tests.rag_eval.harness import Index

    requirements = JDS["backend"]
    before = RESUMES["junior_partial"]
    after = before.replace(
        "Intern, Local Bank (2022)",
        "Deployed services with Docker and Kubernetes on AWS using Redis caching.\nIntern, Local Bank (2022)",
    )
    cov_before = {c.term: c for c in v2_pipeline.coverage(requirements, Index(v2_pipeline.chunker(before)))}
    cov_after = {c.term: c for c in v2_pipeline.coverage(requirements, Index(v2_pipeline.chunker(after)))}

    for term in ("Docker", "Kubernetes", "AWS", "Redis"):
        assert not cov_before[term].covered
        assert cov_after[term].covered
    assert all(cov_after[t].strength >= cov_before[t].strength for t in cov_before)


# --- the owner-run calibration script's pure parts ---------------------------------------------


def test_the_calibration_window_is_suggested_from_the_two_groups():
    from scripts.rag_eval_live import percentile, suggest_window

    covered = [0.72, 0.75, 0.78, 0.80, 0.83, 0.85]
    uncovered = [0.40, 0.45, 0.48, 0.50, 0.52, 0.55]
    suggestion = suggest_window(covered, uncovered)
    assert suggestion["LOW"] == pytest.approx(0.54, abs=0.02)
    assert suggestion["HIGH"] == pytest.approx(0.79, abs=0.02)
    assert suggestion["overlap"] is False and suggestion["gap"] > 0.15
    assert percentile([1, 2, 3, 4], 0.5) == 2.5


def test_overlapping_groups_are_flagged_and_the_window_never_collapses():
    from scripts.rag_eval_live import suggest_window

    suggestion = suggest_window([0.50, 0.55, 0.60], [0.52, 0.58, 0.62])
    assert suggestion["overlap"] is True
    assert suggestion["HIGH"] > suggestion["LOW"]


def test_the_live_script_refuses_to_run_without_a_key_in_the_environment(monkeypatch, capsys):
    import asyncio

    from scripts import rag_eval_live

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert asyncio.run(rag_eval_live.main()) == 2
    assert "GEMINI_API_KEY" in capsys.readouterr().out
