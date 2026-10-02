from app.llm import gateway
from app.llm.json_utils import extract_json
from app.llm.options import LLMOptions
from app.providers.base import Message, MessageRole

# Structured, deterministic, short: JSON mode removes the need for "no markdown"
# instructions, and the cap bounds output.
_OPTIONS = LLMOptions(task="extract", json_mode=True, max_output_tokens=600, temperature=0.0)

_PROMPT = """You are analyzing a job description for an ATS-style resume scoring system.
Extract strictly the following as a single JSON object, with no markdown formatting and no extra commentary:

{{
  "must_have": [list of required skills/qualifications as short strings],
  "nice_to_have": [list of preferred/bonus skills as short strings],
  "experience_level": "entry" | "mid" | "senior" | "lead" | "unspecified",
  "title": "the job title"
}}

Job description:
{jd_text}
"""


_extract_json = extract_json  # kept importable for existing callers/tests


async def extract_requirements(user_id: str, provider: str, jd_text: str) -> dict:
    messages = [Message(role=MessageRole.USER, content=_PROMPT.format(jd_text=jd_text))]
    raw = await gateway.complete(user_id, provider, messages, _OPTIONS)
    data = _extract_json(raw)
    return {
        "must_have": data.get("must_have") or [],
        "nice_to_have": data.get("nice_to_have") or [],
        "experience_level": data.get("experience_level", "unspecified"),
        "title": data.get("title", ""),
    }
