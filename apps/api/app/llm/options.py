from dataclasses import dataclass


@dataclass(frozen=True)
class LLMOptions:
    """Per-call generation settings. `task` selects the model via
    llm.models.model_for -- features name *what* they're doing and the model
    choice lives in one place."""

    task: str = "chat"
    max_output_tokens: int | None = None
    temperature: float | None = None
    json_mode: bool = False


@dataclass
class Usage:
    """Filled in by an adapter as a request completes. Token counts are what
    the provider reported; 0 means "not reported" (callers fall back to
    llm.budget estimates)."""

    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
