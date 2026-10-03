"""The synthetic transcripts used by scripts/report_eval_live.py must be usable
by the real pipeline (and the attack one must be defused in the prompt)."""

from app.interviews.types import get_config
from app.reports.evidence import build_evidence, count_answers
from app.reports.service import MIN_ANSWERS, _messages
from tests.report_eval.golden import QUESTIONS, TRANSCRIPTS, as_turns


def _interview():
    return {"id": "i", "type": "behavioral", "started_at": "2026-10-03T10:00:00+00:00", "brief": "Backend role."}


def test_every_transcript_is_a_full_interview_for_the_pipeline():
    assert set(TRANSCRIPTS) == {"strong", "average", "weak", "attack"}
    for name, answers in TRANSCRIPTS.items():
        assert len(answers) == len(QUESTIONS), name
        turns = as_turns(answers)
        assert count_answers(turns) == len(QUESTIONS) >= MIN_ANSWERS
        ev = build_evidence(_interview(), get_config("behavioral"), turns)
        assert ev.answer_count == len(QUESTIONS) and ev.omitted_turns == 0


def test_strong_answers_are_longer_and_more_specific_than_weak_ones():
    words = {k: sum(len(a.split()) for a in v) for k, v in TRANSCRIPTS.items()}
    assert words["strong"] > words["average"] > words["weak"]


def test_the_attack_transcript_cannot_forge_our_delimiters():
    ev = build_evidence(_interview(), get_config("behavioral"), as_turns(TRANSCRIPTS["attack"]))
    user = _messages(_interview(), get_config("behavioral"), ev, [], None)[1].content
    assert "[tag removed]" in user and user.count("</data") == user.count("<data kind")
