from app.interviews.types import InterviewTypeConfig


def phase_for_elapsed(config: InterviewTypeConfig, elapsed_minutes: float) -> str:
    """Which phase should be active given how many minutes have elapsed
    since the interview started. Clamps to the final phase once the total
    duration has passed, rather than raising -- a slightly-overrunning
    interview should still resolve to "wrap_up", not error."""
    cumulative = 0
    for name, duration in config.phases:
        cumulative += duration
        if elapsed_minutes < cumulative:
            return name
    return config.phases[-1][0]


def minutes_remaining(config: InterviewTypeConfig, elapsed_minutes: float) -> float:
    return max(0.0, config.total_minutes - elapsed_minutes)


def is_final_phase(config: InterviewTypeConfig, phase: str) -> bool:
    return bool(config.phases) and config.phases[-1][0] == phase
