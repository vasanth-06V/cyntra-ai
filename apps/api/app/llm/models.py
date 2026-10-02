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
    },
    "claude": {
        "chat": _CLAUDE_STRONG,
        "interview": _CLAUDE_STRONG,
        "feedback": _CLAUDE_STRONG,
        "extract": _CLAUDE_FAST,
        "summarize": _CLAUDE_FAST,
        "validate": _CLAUDE_FAST,
    },
    "groq": {
        "chat": _GROQ_STRONG,
        "interview": _GROQ_STRONG,
        "feedback": _GROQ_STRONG,
        "extract": _GROQ_FAST,
        "summarize": _GROQ_FAST,
        "validate": _GROQ_FAST,
    },
}


def model_for(provider: str, task: str) -> str:
    try:
        return MODELS[provider][task]
    except KeyError as exc:
        raise ValueError(f"No model configured for provider={provider!r} task={task!r}") from exc
