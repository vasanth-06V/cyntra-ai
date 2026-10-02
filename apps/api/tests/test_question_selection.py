import random

import pytest

from app.interviews.question_selection import select_questions


def cand(qid, sim, vec, topic=None, difficulty=None):
    return {"id": qid, "similarity": sim, "embedding": str(vec), "topic": topic, "difficulty": difficulty}


def rng():
    return random.Random(7)


def test_the_most_relevant_question_goes_first():
    picked = select_questions([cand("b", 0.60, [0, 1]), cand("a", 0.90, [1, 0])], 1, rng())
    assert [q["id"] for q in picked] == ["a"]


def test_near_duplicates_are_not_picked_together():
    candidates = [
        cand("lists-1", 0.90, [1.0, 0.0, 0.0], topic="lists"),
        cand("lists-2", 0.89, [0.99, 0.05, 0.0], topic="lists"),  # almost the same question
        cand("graphs", 0.80, [0.0, 1.0, 0.0], topic="graphs"),
    ]
    picked = select_questions(candidates, 2, rng())
    assert {q["id"] for q in picked} == {"lists-1", "graphs"}


def test_an_already_chosen_topic_is_penalised_even_when_vectors_differ():
    candidates = [
        cand("arr-1", 0.90, [1.0, 0.0, 0.0], topic="arrays"),
        cand("arr-2", 0.88, [0.2, 0.9, 0.0], topic="arrays"),
        cand("dp", 0.80, [0.0, 0.0, 1.0], topic="dp"),
    ]
    picked = select_questions(candidates, 2, rng())
    assert [q["id"] for q in picked] == ["arr-1", "dp"]


def test_a_pure_relevance_setting_would_have_taken_the_near_duplicate():
    candidates = [cand("a", 0.90, [1.0, 0.0]), cand("a2", 0.89, [0.99, 0.05]), cand("b", 0.5, [0.0, 1.0])]
    assert {q["id"] for q in select_questions(candidates, 2, rng(), mmr_lambda=1.0)} == {"a", "a2"}


def test_equally_good_questions_vary_between_runs_but_clearly_better_ones_do_not():
    close = [cand("x", 0.800, [1, 0]), cand("y", 0.801, [0, 1])]
    firsts = {select_questions(close, 1, random.Random(seed))[0]["id"] for seed in range(40)}
    assert firsts == {"x", "y"}  # a coin flip between near-ties

    clear = [cand("x", 0.90, [1, 0]), cand("y", 0.60, [0, 1])]
    assert {select_questions(clear, 1, random.Random(seed))[0]["id"] for seed in range(40)} == {"x"}


def test_selection_never_returns_more_than_exist_and_handles_empty_input():
    assert select_questions([], 2) == []
    assert select_questions([cand("a", 0.9, [1, 0])], 3, rng())[0]["id"] == "a"
    assert len(select_questions([cand("a", 0.9, [1, 0])], 3, rng())) == 1
    assert select_questions([cand("a", 0.9, [1, 0])], 0) == []


def test_embeddings_may_arrive_as_database_text_or_lists_and_helper_keys_do_not_leak():
    picked = select_questions([{"id": "a", "similarity": 0.9, "embedding": "[0.1, 0.2, 0.3]", "topic": None}], 1, rng())
    assert set(picked[0]) == {"id", "similarity", "embedding", "topic"}
    assert select_questions([{"id": "b", "similarity": 0.5, "embedding": [0.1, 0.2], "topic": None}], 1, rng())[0]["id"] == "b"
