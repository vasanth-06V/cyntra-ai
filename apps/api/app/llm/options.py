from dataclasses import dataclass, field


@dataclass(frozen=True)
class LLMOptions:
    """Per-call generation settings. `task` selects the model via
    llm.models.model_for -- features name *what* they're doing and the model
    choice lives in one place."""

    task: str = "chat"
    max_output_tokens: int | None = None
    temperature: float | None = None
    json_mode: bool = False
    # Seconds before the provider call is abandoned; None = the task default
    # from llm.models.timeout_for.
    timeout_s: float | None = None
    # Which product feature is calling (chat, interview_turn, ats_feedback, ...):
    # carried into logs and usage so consumption can be broken down.
    feature: str | None = None
    # "interactive" calls (a user is waiting) go ahead of "background" ones
    # (summaries, digests) when the per-key limiter has to queue.
    priority: str = "interactive"
    # Which prompt template produced this call, for tracing stored output.
    prompt_id: str | None = None
    prompt_version: str | None = None
    # On a truncated reply (finish_reason == "length") cut back to the last
    # complete sentence instead of showing a half sentence.
    trim_on_length: bool = False
    # Use this model instead of the one models.py picks for the task (set by
    # the gateway when walking a fallback list).
    model_override: str | None = None


@dataclass
class Usage:
    """Filled in by an adapter as a request completes. Token counts are what
    the provider reported; 0 means "not reported" (callers fall back to
    llm.budget estimates)."""

    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    # Reasoning ("thinking") tokens: billed like output but reported apart.
    thought_tokens: int = 0
    cached_tokens: int = 0
    # Normalized: "stop" | "length" | "blocked" | "refusal" | "other" | None
    finish_reason: str | None = None
    model: str | None = None
    # Milliseconds from sending the request to the first streamed text.
    ttft_ms: float | None = None
    extra: dict = field(default_factory=dict)
