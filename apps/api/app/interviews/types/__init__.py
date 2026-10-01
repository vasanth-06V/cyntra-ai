from dataclasses import dataclass

from app.interviews.types import (
    behavioral,
    case_study,
    coding,
    hr,
    ml_ai,
    sde,
    system_design,
    webd,
)


@dataclass(frozen=True)
class InterviewTypeConfig:
    phases: list[tuple[str, int]]  # (phase_name, duration_minutes), in order
    needs_coding_platform: bool
    question_count: int
    system_prompt: str

    @property
    def total_minutes(self) -> int:
        return sum(duration for _, duration in self.phases)


_MODULES = {
    "coding": coding,
    "behavioral": behavioral,
    "hr": hr,
    "ml_ai": ml_ai,
    "webd": webd,
    "sde": sde,
    "system_design": system_design,
    "case_study": case_study,
}

_REGISTRY: dict[str, InterviewTypeConfig] = {
    name: InterviewTypeConfig(
        phases=module.PHASES,
        needs_coding_platform=module.NEEDS_CODING_PLATFORM,
        question_count=module.QUESTION_COUNT,
        system_prompt=module.SYSTEM_PROMPT,
    )
    for name, module in _MODULES.items()
}


def get_config(interview_type: str) -> InterviewTypeConfig:
    try:
        return _REGISTRY[interview_type]
    except KeyError as exc:
        raise ValueError(f"Unknown interview type: {interview_type}") from exc
