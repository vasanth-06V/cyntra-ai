from app.llm import gateway
from app.llm.options import LLMOptions
from app.llm.prompts.ats import FEEDBACK_PROMPT
from app.providers.base import Message, MessageRole

_OPTIONS = LLMOptions(
    task="feedback",
    max_output_tokens=400,
    temperature=0.4,
    trim_on_length=True,
    feature="ats_feedback",
    prompt_id="ats.feedback",
    prompt_version="1",
)

async def generate_feedback(
    user_id: str,
    provider: str,
    title: str,
    missing_must_have: list[str],
    missing_nice_to_have: list[str],
    keyword_score: float,
    semantic_score: float,
    formatting_score: float,
) -> str:
    prompt = FEEDBACK_PROMPT.format(
        title=title or "this role",
        missing_must_have=", ".join(missing_must_have) or "none",
        missing_nice_to_have=", ".join(missing_nice_to_have) or "none",
        keyword_score=keyword_score,
        semantic_score=semantic_score,
        formatting_score=formatting_score,
    )
    messages = [Message(role=MessageRole.USER, content=prompt)]
    text = await gateway.complete(user_id, provider, messages, _OPTIONS)
    return text.strip()
