"""The labels in the golden set must be TRUE, or the live measurement
(scripts/judge_eval_live.py) would blame the model for our mistakes. Python
cases are executed here; the other languages are labelled by construction
(each wrong one is a single, easily checked defect)."""

from app.coding.schemas import ReviewOut
from tests.judge_eval.golden import CASES, PROBLEMS


def _function(source: str, name: str):
    namespace: dict = {}
    exec(source, namespace)  # noqa: S102 - our own fixed test data
    return namespace[name]


def _passes(source: str, name: str, checks) -> list[bool]:
    fn = _function(source, name)
    results = []
    for args, expected in checks:
        copied = [[list(x) if isinstance(x, list) else x for x in a] if isinstance(a, list) else a for a in args]
        try:
            results.append(fn(*copied) == expected)
        except Exception:
            results.append(False)
    return results


def test_the_reference_solutions_pass_their_own_checks():
    checks = {
        "unique_substring": ("length_of_longest_substring", [(("abcabcbb",), 3), (("bbbbb",), 1), (("pwwkew",), 3), (("",), 0), (("abba",), 2)]),
        "merge_intervals": ("merge", [(([[1, 3], [2, 6], [8, 10], [15, 18]],), [[1, 6], [8, 10], [15, 18]]), (([[1, 2], [2, 3]],), [[1, 3]]), (([],), []), (([[5, 6], [1, 2]],), [[1, 2], [5, 6]])]),
    }
    for key, (name, cases) in checks.items():
        assert all(_passes(PROBLEMS[key]["solution_code"], name, cases)), key


def test_every_python_label_is_true():
    executed = 0
    for case in CASES:
        if "run" not in case:
            continue
        name, checks = case["run"]
        results = _passes(case["code"], name, checks)
        if case["expected"] == "correct":
            assert all(results), f"{case['id']} is labelled correct but fails a check: {results}"
        else:
            assert not all(results), f"{case['id']} is labelled wrong but passes every check"
        executed += 1
    assert executed == 6  # the six Python cases


def test_the_set_is_balanced_and_multi_language():
    assert len(CASES) == 12 and len({c["id"] for c in CASES}) == 12
    assert sum(c["expected"] == "correct" for c in CASES) == 6
    assert {c["language"] for c in CASES} >= {"Python", "JavaScript", "C++", "TypeScript"}
    assert all(c["problem"] in PROBLEMS for c in CASES)
    for problem in PROBLEMS.values():
        assert problem["solution_code"].strip() and problem["question"].strip()


def test_a_reviewer_answer_parses_with_the_real_schema():
    ReviewOut.model_validate({
        "trace": "For 'abba' it returns 2 at line 6 because start is moved only forward.",
        "approach": "same_as_reference", "result": "correct", "interviewer_message": "Thanks. What is the complexity?",
    })
