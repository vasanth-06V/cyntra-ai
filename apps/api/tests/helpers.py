from app.llm.completion import Completion
from app.llm.options import Usage


def completion(text: str, finish: str | None = "stop") -> Completion:
    """A gateway Completion for tests that replace gateway.complete_full."""
    return Completion(
        text=text,
        finish_reason=finish,
        usage=Usage(requests=1, finish_reason=finish),
        provider="gemini",
        model="test-model",
        latency_ms=1.0,
    )
