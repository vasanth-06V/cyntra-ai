import hashlib

from fastapi import HTTPException, status

from app.llm import gateway
from app.llm.gateway import StructuredOutputError
from app.llm.schemas import RequirementsOut
from app.llm.budget import truncate
from app.llm.json_utils import extract_json
from app.llm.prompts.ats import REQUIREMENTS_PROMPT
from app.llm.ttl_cache import TTLCache
from app.llm.options import LLMOptions
from app.providers.base import Message, MessageRole

# Structured, deterministic, short: JSON mode removes the need for "no markdown"
# instructions, and the cap bounds output.
_OPTIONS = LLMOptions(
    task="extract",
    json_mode=True,
    max_output_tokens=600,
    temperature=0.0,
    feature="ats_requirements",
    prompt_id="ats.requirements",
    prompt_version="1",
)

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
    try:
        parsed = await gateway.complete_structured(
            user_id, provider, [Message(role=MessageRole.USER, content=prompt)], RequirementsOut, _OPTIONS
        )
    except StructuredOutputError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The model returned an unreadable analysis of the job description -- please try again.",
        ) from exc
    result = parsed.model_dump()
    _cache.set(key, result)
    return result
