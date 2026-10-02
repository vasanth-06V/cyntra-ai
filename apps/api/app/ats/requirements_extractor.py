import hashlib

from app.llm import gateway
from app.llm.budget import truncate
from app.llm.json_utils import extract_json
from app.llm.prompts.ats import REQUIREMENTS_PROMPT
from app.llm.ttl_cache import TTLCache
from app.llm.options import LLMOptions
from app.providers.base import Message, MessageRole

# Structured, deterministic, short: JSON mode removes the need for "no markdown"
# instructions, and the cap bounds output.
_OPTIONS = LLMOptions(task="extract", json_mode=True, max_output_tokens=600, temperature=0.0)

_JD_TOKEN_BUDGET = 1500
_cache = TTLCache(ttl_seconds=3600)

_extract_json = extract_json  # kept importable for existing callers/tests


async def extract_requirements(user_id: str, provider: str, jd_text: str) -> dict:
    # Re-scoring the same JD against another resume costs no LLM call. Keyed by
    # user too, so one user's JD is never served to another.
    key = (user_id, hashlib.sha256(jd_text.encode()).hexdigest())
    cached = _cache.get(key)
    if cached is not None:
        return cached

    prompt = REQUIREMENTS_PROMPT.format(jd_text=truncate(jd_text, _JD_TOKEN_BUDGET))
    raw = await gateway.complete(
        user_id, provider, [Message(role=MessageRole.USER, content=prompt)], _OPTIONS
    )
    data = _extract_json(raw)
    result = {
        "must_have": data.get("must_have") or [],
        "nice_to_have": data.get("nice_to_have") or [],
        "experience_level": data.get("experience_level", "unspecified"),
        "title": data.get("title", ""),
    }
    _cache.set(key, result)
    return result
