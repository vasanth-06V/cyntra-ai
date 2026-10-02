from dataclasses import dataclass

from app.llm.options import Usage


@dataclass
class Completion:
    """A finished (non-streaming) model reply plus how it ended."""

    text: str
    # "stop" | "length" | "blocked" | "refusal" | "other" | None (not reported)
    finish_reason: str | None
    usage: Usage
    provider: str
    model: str | None
    latency_ms: float
    attempts: int = 1
    failed_over: bool = False

    @property
    def truncated(self) -> bool:
        return self.finish_reason == "length"
