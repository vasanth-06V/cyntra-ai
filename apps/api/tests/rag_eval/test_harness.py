"""The harness itself must be trustworthy before it is used to judge anything."""

import math

from . import fake_embedder as fe
from . import harness as h
from .golden import EVIDENCE, EXPECTED_SECTIONS, JDS, RANKING, RESUMES


def test_embedder_is_deterministic_and_normalized():
    a, b = fe.embed("Python developer"), fe.embed("Python developer")
    assert a == b
    assert math.sqrt(sum(x * x for x in a)) == pytest_approx(1.0)
    assert len(a) == fe.DIMENSIONS


def pytest_approx(value):
    import pytest

    return pytest.approx(value, abs=1e-9)


def test_shared_vocabulary_is_similar_and_unrelated_text_is_not():
    query = fe.embed("kubernetes")
    related = fe.embed("Operated production Kubernetes clusters on AWS")
    unrelated = fe.embed("Planned email campaigns and managed the marketing budget")
    assert fe.cosine(query, related) > 0.25 > fe.cosine(query, unrelated) + 0.1


def test_synonyms_are_folded():
    assert fe.cosine(fe.embed("k8s"), fe.embed("kubernetes")) > 0.99
    assert fe.cosine(fe.embed("Postgres"), fe.embed("PostgreSQL")) > 0.99


def test_golden_data_is_internally_consistent():
    assert set(EVIDENCE) <= set(RESUMES) and set(EXPECTED_SECTIONS) == set(RESUMES)
    for jd, groups in RANKING.items():
        assert jd in JDS
        assert {r for names in groups.values() for r in names} <= set(RESUMES)
    # every claimed piece of evidence really is in the resume text
    for resume, by_jd in EVIDENCE.items():
        for terms in by_jd.values():
            for term in terms:
                folded = {"postgresql": ("postgres", "postgresql")}.get(term, (term,))
                assert any(f in RESUMES[resume].lower() for f in folded), (resume, term)


def test_chunk_stats_counts_lines_cut_in_the_middle():
    text = "Experience\nBuilt services.\nLed the team through a migration of services.\n"
    clean = [h.EvalChunk(body=text.strip(), content=text.strip())]
    cut = [h.EvalChunk(body="Led the team through a migr", content="Led the team through a migr")]
    assert h.chunk_stats(text, clean)["cut_mid_line"] == 0
    assert h.chunk_stats(text, cut)["cut_mid_line"] >= 1


def test_section_recall_uses_labels_or_leading_heading_text():
    chunks = [
        h.EvalChunk(body="Experience\nBuilt things", content="x", section=None),
        h.EvalChunk(body="Built other things", content="x", section="education"),
    ]
    assert h.section_recall("junior_partial", chunks) == 2 / 3  # experience + education of the 3 expected


def test_ranking_quality_detects_a_wrong_order():
    good = {"strong_backend": 80, "caps_style": 75, "messy_layout": 50, "junior_partial": 40, "weak_unrelated": 10, "frontend_dev": 12}
    bad = dict(good, weak_unrelated=90)
    assert h.ranking_quality("backend", good)["pair_accuracy"] == 1.0
    assert h.ranking_quality("backend", bad)["pair_accuracy"] < 1.0
