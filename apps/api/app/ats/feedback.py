from app.ats.llm_utils import complete_text
from app.providers.base import Message, MessageRole

_PROMPT = """You are giving a candidate actionable feedback on how well their \
resume matches a job description, for an ATS-style resume scoring tool.

Job title: {title}
Missing must-have requirements: {missing_must_have}
Missing nice-to-have requirements: {missing_nice_to_have}
Keyword match score: {keyword_score:.0%}
Semantic relevance score: {semantic_score:.0%}
Formatting score: {formatting_score:.0%}

Write 3-5 short, specific, actionable bullet points the candidate can use to \
improve their resume for this job. Mention concrete keywords to add where \
relevant, and only flag formatting concerns if the formatting score is low. \
Give advice, not a report -- do not just repeat the scores back.
"""


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
    prompt = _PROMPT.format(
        title=title or "this role",
        missing_must_have=", ".join(missing_must_have) or "none",
        missing_nice_to_have=", ".join(missing_nice_to_have) or "none",
        keyword_score=keyword_score,
        semantic_score=semantic_score,
        formatting_score=formatting_score,
    )
    messages = [Message(role=MessageRole.USER, content=prompt)]
    text = await complete_text(user_id, provider, messages)
    return text.strip()
