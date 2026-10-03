"""Task -> model, per provider. The one place to edit when a provider retires
a model (it already happened once: gemini-1.5-flash).

Gemini uses the *lite* "-latest" alias deliberately: measured 6-7s to first
token for gemini-flash-latest (a "thinking" model) vs ~0.9s for
gemini-flash-lite-latest, and a far higher free-tier daily quota. Chat and
the voice interviews need low latency more than maximum depth.

IDs last verified against the providers' docs on 2026-10-02 (see docs/FACTS.md);
not yet exercised with a live key. Re-check before relying on a name: Claude Haiku
4.5 is announced to retire no sooner than 2026-10-15, so the "fast" tier points at
Sonnet 5.5 as well until that is re-evaluated.
"""

EMBEDDING_MODEL = "models/gemini-embedding-001"
EMBEDDING_DIMENSIONS = 768  # matches the vector(768) columns
# Written on every embedded row (once those columns exist) so a later model or
# task-type change can find stale vectors.
EMBEDDING_VERSION = "gemini-embedding-001:768:v2"

_GEMINI = "gemini-flash-lite-latest"
_CLAUDE_STRONG = "claude-sonnet-5-5"
_CLAUDE_FAST = _CLAUDE_STRONG
_GROQ_FAST = "llama-3.1-8b-instant"
_GROQ_STRONG = "llama-3.3-70b-versatile"

# Cheap, structured tasks (extract/summarize/validate) can use the fast tier;
# anything the user reads as a conversation uses the stronger one.
MODELS: dict[str, dict[str, str]] = {
    "gemini": {
        "chat": _GEMINI,
        "interview": _GEMINI,
        "feedback": _GEMINI,
        "extract": _GEMINI,
        "summarize": _GEMINI,
        "validate": _GEMINI,
        "judge": _GEMINI,
    },
    "claude": {
        "chat": _CLAUDE_STRONG,
        "interview": _CLAUDE_STRONG,
        "feedback": _CLAUDE_STRONG,
        "extract": _CLAUDE_FAST,
        "summarize": _CLAUDE_FAST,
        "validate": _CLAUDE_FAST,
        "judge": _CLAUDE_STRONG,
    },
    "groq": {
        "chat": _GROQ_STRONG,
        "interview": _GROQ_STRONG,
        "feedback": _GROQ_STRONG,
        "extract": _GROQ_FAST,
        "summarize": _GROQ_FAST,
        "validate": _GROQ_FAST,
        "judge": _GROQ_STRONG,
    },
}

# Seconds a single provider call may take (for streams: the longest silence
# between chunks) before it is abandoned. Without these the SDK defaults apply
# -- up to 10 minutes -- which would freeze a live interview turn.
TIMEOUTS: dict[str, float] = {
    "chat": 60.0,
    "interview": 25.0,
    "feedback": 40.0,
    "extract": 30.0,
    "summarize": 30.0,
    "validate": 15.0,
    "judge": 45.0,
}
DEFAULT_TIMEOUT = 30.0

# Gemini lite-class models "think" by default and thought tokens count against
# maxOutputTokens, which would silently truncate our tight caps. Per model:
#   thinking_config -- sent as generationConfig.thinkingConfig to keep thinking
#                      minimal (None = send nothing, e.g. models that don't think)
#   allowance       -- extra output tokens added to the caller's cap to cover
#                      whatever thinking still happens
# The adapter self-heals: if the API rejects thinkingConfig it retries without
# it and stops sending it for the rest of the process. Verify with the
# user-run smoke script (scripts/llm_smoke.py).
GEMINI_MODEL_TRAITS: dict[str, dict] = {
    "gemini-flash-lite-latest": {"thinking_config": {"thinkingLevel": "minimal"}, "allowance": 256},
}
_DEFAULT_GEMINI_TRAITS: dict = {"thinking_config": None, "allowance": 256}

# If a model is retired or unknown (404), these are tried in order. Pin explicit
# IDs here for production once they are verified; `-latest` aliases can change
# underneath you.
FALLBACKS: dict[str, dict[str, list[str]]] = {
    "gemini": {},
    "claude": {},
    "groq": {},
}


def model_for(provider: str, task: str) -> str:
    try:
        return MODELS[provider][task]
    except KeyError as exc:
        raise ValueError(f"No model configured for provider={provider!r} task={task!r}") from exc


def timeout_for(task: str) -> float:
    return TIMEOUTS.get(task, DEFAULT_TIMEOUT)


def gemini_traits(model: str) -> dict:
    return GEMINI_MODEL_TRAITS.get(model, _DEFAULT_GEMINI_TRAITS)
