"""Interview start picks questions the user has not met yet, without ever
shipping the answer key, and degrades to repeats rather than a short interview."""

from .conftest import USER_A, USER_B
from .test_interview_flow import _seed_questions, _start, keyed  # noqa: F401  (fixture reuse)


def _selected(env, interview_id):
    return env.db.rows("interviews", id=interview_id)[0]["selected_question_ids"]


async def test_a_second_interview_gets_the_questions_the_first_did_not(client, keyed):
    bank = {q["id"] for q in _seed_questions(keyed, 4, "coding")}

    first, _ = await _start(client, keyed)
    second, _ = await _start(client, keyed)

    one, two = set(_selected(keyed, first.json()["id"])), set(_selected(keyed, second.json()["id"]))
    assert len(one) == len(two) == 2 and one.isdisjoint(two)  # nothing repeated while fresh ones exist
    assert one | two == bank


async def test_when_the_bank_is_used_up_questions_repeat_instead_of_the_interview_being_short(client, keyed):
    _seed_questions(keyed, 2, "coding")

    await _start(client, keyed)
    again, _ = await _start(client, keyed)

    assert len(_selected(keyed, again.json()["id"])) == 2


async def test_another_users_history_does_not_affect_me(client, keyed):
    bank = {q["id"] for q in _seed_questions(keyed, 2, "coding")}

    await _start(client, keyed, user=USER_A)
    other, _ = await _start(client, keyed, user=USER_B)

    assert set(_selected(keyed, other.json()["id"])) == bank


async def test_only_questions_of_the_interview_type_are_candidates(client, keyed):
    _seed_questions(keyed, 3, "hr")  # wrong type for a coding interview
    started, _ = await _start(client, keyed, type_="coding", seed_bank=False)
    assert started.status_code == 422 and started.json()["error"]["code"] == "no_questions"  # none of them was chosen


async def test_the_retrieval_call_never_asks_for_or_receives_test_cases(client, keyed):
    keyed.db.seed("question_bank", type="coding", question="Q", embedding=[0.1, 0.2, 0.3], test_cases=[{"input": "1", "output": "2"}])
    await _start(client, keyed)
    name, params = next(c for c in keyed.db.rpc_calls if c[0] == "match_question_bank_v2")
    assert "test_cases" not in str(params)
    rows = keyed.db.run_rpc("match_question_bank_v2", params)
    assert all("test_cases" not in row for row in rows)
