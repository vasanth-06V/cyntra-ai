from app.providers.base import ProviderAdapter
from app.providers.claude import ClaudeAdapter
from app.providers.gemini import GeminiAdapter
from app.providers.groq import GroqAdapter

_ADAPTERS: dict[str, ProviderAdapter] = {
    "gemini": GeminiAdapter(),
    "claude": ClaudeAdapter(),
    "groq": GroqAdapter(),
}


def get_adapter(provider: str) -> ProviderAdapter:
    try:
        return _ADAPTERS[provider]
    except KeyError as exc:
        raise ValueError(f"Unknown provider: {provider}") from exc
