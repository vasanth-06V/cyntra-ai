from app.interviews.orchestrator import is_final_phase, minutes_remaining, phase_for_elapsed
from app.interviews.types import get_config


def test_phase_for_elapsed_returns_first_phase_at_start():
    config = get_config("coding")  # intro(5), problem_1(25), problem_2(25), wrap_up(5)
    assert phase_for_elapsed(config, 0) == "intro"
    assert phase_for_elapsed(config, 4.9) == "intro"


def test_phase_for_elapsed_advances_through_phases():
    config = get_config("coding")
    assert phase_for_elapsed(config, 5) == "problem_1"
    assert phase_for_elapsed(config, 29.9) == "problem_1"
    assert phase_for_elapsed(config, 30) == "problem_2"
    assert phase_for_elapsed(config, 55) == "wrap_up"


def test_phase_for_elapsed_clamps_to_final_phase_when_overrun():
    config = get_config("coding")
    assert phase_for_elapsed(config, 999) == "wrap_up"


def test_minutes_remaining_counts_down_and_floors_at_zero():
    config = get_config("behavioral")  # total 60
    assert minutes_remaining(config, 0) == 60
    assert minutes_remaining(config, 30) == 30
    assert minutes_remaining(config, 999) == 0


def test_is_final_phase():
    config = get_config("hr")
    assert is_final_phase(config, "wrap_up") is True
    assert is_final_phase(config, "warm_up") is False


def test_all_interview_types_sum_to_sixty_minutes():
    for interview_type in [
        "coding",
        "behavioral",
        "hr",
        "ml_ai",
        "webd",
        "sde",
        "system_design",
        "case_study",
    ]:
        config = get_config(interview_type)
        assert config.total_minutes == 60, f"{interview_type} does not sum to 60 minutes"
