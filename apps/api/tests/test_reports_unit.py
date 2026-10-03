"""The deterministic parts of reports: scoring, caps, quote checks, evidence
trimming and the tolerant schema."""

import pytest
from pydantic import ValidationError

from app.interviews.types import get_config
from app.reports import scoring
from app.reports.evidence import build_evidence, coding_facts, count_answers
from app.reports.schemas import ReportOut


def _dims(**scores):
    return {k: {"score": v, "reason": "because"} for k, v in scores.items()}


# ------------------------------------------------------------------ scoring


def test_overall_is_the_weighted_mean_of_scored_dimensions():
    all_fives = {"communication": 5, "structure": 5, "technical_depth": 5, "role_relevance": 5, "coding_quality": 5}
    assert scoring.overall_score("coding", all_fives) == 100
    all_ones = {k: 1 for k in all_fives}
    assert scoring.overall_score("coding", all_ones) == 20
    # technical depth carries more weight than communication in a coding interview
    strong_tech = {"technical_depth": 5, "communication": 1, "structure": 3, "role_relevance": 3, "coding_quality": None}
    strong_talk = {"technical_depth": 1, "communication": 5, "structure": 3, "role_relevance": 3, "coding_quality": None}
    assert scoring.overall_score("coding", strong_tech) > scoring.overall_score("coding", strong_talk)


def test_unscored_dimensions_do_not_drag_the_score_down():
    with_code = {"communication": 4, "structure": 4, "technical_depth": 4, "role_relevance": 4, "coding_quality": 4}
    without = {**with_code, "coding_quality": None}
    assert scoring.overall_score("coding", with_code) == scoring.overall_score("coding", without) == 80
    assert scoring.overall_score("hr", {}) == 0


def test_the_coding_score_cannot_beat_the_stored_code_review():
    base = {"communication": 4, "coding_quality": 5}
    assert scoring.apply_caps(base, ["correct"])["coding_quality"] == 5
    assert scoring.apply_caps(base, ["mostly_correct"])["coding_quality"] == 4
    assert scoring.apply_caps(base, ["incorrect"])["coding_quality"] == 2
    assert scoring.apply_caps(base, ["correct", "incomplete"])["coding_quality"] == 2  # the strictest problem rules
    assert scoring.apply_caps(base, [])["coding_quality"] is None  # no code, nothing to score
    assert scoring.apply_caps({"communication": 4}, ["correct"]).get("coding_quality") is None


def test_bands():
    assert [scoring.band(s) for s in (95, 80, 79, 60, 59, 40, 39, 0)] == [
        "Strong", "Strong", "Good", "Good", "Developing", "Developing", "Needs work", "Needs work",
    ]


def test_quotes_must_really_be_in_an_answer():
    answers = ["I would use a hash map to store the seen values, then scan once.", "We shipped it in two weeks."]
    assert scoring.quote_is_real("use a HASH MAP to store the seen values", answers)  # case/punctuation ignored
    assert not scoring.quote_is_real("I would use a heap to store the seen values", answers)  # invented
    assert not scoring.quote_is_real("hash map", answers)  # too short to mean anything
    assert not scoring.quote_is_real("then scan once. We shipped it in two weeks", answers)  # stitched across answers
    assert not scoring.quote_is_real(None, answers)


# ------------------------------------------------------------------ evidence


def _turn(i, speaker, text, minute=0):
    return {"turn_index": i, "speaker": speaker, "text": text, "created_at": f"2026-10-03T10:{minute:02d}:00+00:00"}


def _interview():
    return {"started_at": "2026-10-03T10:00:00+00:00", "type": "coding"}


def test_evidence_counts_answers_and_places_them_in_phases():
    turns = [
        _turn(0, "ai", "Welcome!", 0),
        _turn(1, "user", "Hi, I am a backend engineer with five years of experience.", 2),
        _turn(2, "ai", "Problem one: two sum.", 6),
        _turn(3, "user", "I would use a hash map.", 8),
        _turn(4, "user", "[Submitted a solution in Python · 6 lines]", 20),  # a marker, not speech
        _turn(5, "ai", "How does it scale?", 21),
        _turn(6, "user", "Linear time and linear space.", 23),
    ]
    ev = build_evidence(_interview(), get_config("coding"), turns)
    assert ev.answer_count == 3 and count_answers(turns) == 3
    assert "Submitted a solution" not in " ".join(ev.answers)  # never quotable
    assert [p["answers"] for p in ev.phases] == [1, 2, 0, 0]  # intro, problem_1, problem_2, wrap_up
    assert ev.minutes_used == 23.0
    assert "Interviewer: Welcome!" in ev.transcript and "Candidate: I would use a hash map." in ev.transcript


def test_a_long_transcript_keeps_the_opening_and_the_latest_turns():
    turns = [_turn(0, "ai", "Welcome and tell me about yourself.", 0)]
    for i in range(1, 80):
        turns.append(_turn(i, "user" if i % 2 else "ai", f"turn number {i} " + "word " * 120, 1 + i // 3))
    ev = build_evidence(_interview(), get_config("coding"), turns, budget_tokens=1500)
    assert ev.omitted_turns > 0 and "turns omitted" in ev.transcript
    assert "Welcome and tell me about yourself." in ev.transcript  # opening kept
    assert "turn number 79" in ev.transcript or "turn number 78" in ev.transcript  # the end kept
    assert "turn number 20 " not in ev.transcript  # the middle went


def test_each_answer_is_capped_so_one_monologue_cannot_eat_the_budget():
    turns = [_turn(0, "ai", "Q?", 0), _turn(1, "user", "blah " * 5000, 1)]
    ev = build_evidence(_interview(), get_config("coding"), turns)
    assert len(ev.transcript) < 1500 and len(ev.answers[0]) > 20000  # the full text stays available for quote checks


def test_coding_facts_use_the_stored_verdicts_in_problem_order():
    verdict = {"result": "mostly_correct", "approach": "different_but_valid", "issues": ["slow"],
               "edge_cases_missed": [], "candidate_complexity": "O(n^2)", "reference_complexity": "O(n)"}
    subs = [
        {"question_id": "q2", "language": "C++", "line_count": 20, "status": "done", "verdict": {**verdict, "result": "correct"}},
        {"question_id": "q1", "language": "Python", "line_count": 6, "status": "done", "verdict": verdict},
        {"question_id": "q1", "language": "Python", "line_count": 6, "status": "failed", "verdict": None},
    ]
    facts = coding_facts(subs, ["q1", "q2"])
    assert [(f["problem"], f["language"], f["result"]) for f in facts] == [(1, "Python", "mostly_correct"), (2, "C++", "correct")]


# ------------------------------------------------------------------ schema


def test_the_schema_tolerates_sloppy_model_output():
    out = ReportOut.model_validate({
        "verdict": "Solid.",
        "dimensions": {
            "communication": {"score": "4/5", "reason": "clear"},
            "technical_depth": {"score": 9},  # out of range -> 5
            "structure": {"score": None},  # no evidence
            "made_up_dimension": {"score": 5},  # ignored
        },
        "strengths": ["Good examples", {"point": "Clear", "quote": "I led the migration"}, 7],
        "improvements": "Add numbers",
        "next_steps": ["a", "b", "c", "d"],
        "overall_score": 100,  # never read
    })
    assert out.dimensions["communication"].score == 4 and out.dimensions["technical_depth"].score == 5
    assert out.dimensions["structure"].score is None and "made_up_dimension" not in out.dimensions
    assert [s.point for s in out.strengths] == ["Good examples", "Clear"]
    assert [s.point for s in out.improvements] == ["Add numbers"]
    assert len(out.next_steps) == 3
    assert not hasattr(out, "overall_score")


def test_a_report_must_score_at_least_two_dimensions():
    with pytest.raises(ValidationError):
        ReportOut.model_validate({"dimensions": {"communication": {"score": 4}}})
    with pytest.raises(ValidationError):
        ReportOut.model_validate({"dimensions": "none"})
