import asyncio

from app.core.db import get_supabase
from app.llm import gateway
from app.llm.options import LLMOptions
from app.providers.base import Message, MessageRole

_OPTIONS = LLMOptions(task="summarize", max_output_tokens=250, temperature=0.2)

SUMMARIZE_EVERY_N_TURNS = 6

_SUMMARY_PROMPT = """Summarize the following interview conversation so far in 3-5 \
sentences, capturing what topics/questions have been covered and how the \
candidate has performed, so this summary can replace the full transcript in \
future context. Be factual and concise.

Previous summary (if any): {previous_summary}

Full conversation so far:
{turns_text}
"""


async def maybe_update_summary(interview_id: str, user_id: str, provider: str) -> None:
    """Keeps token usage flat as an interview gets long (Section 8.3): every
    SUMMARIZE_EVERY_N_TURNS turns, collapse the transcript into a running
    summary so future LLM calls use summary + recent turns instead of the
    full history."""
    supabase = get_supabase()

    def _count_turns():
        return (
            supabase.table("interview_transcripts")
            .select("id", count="exact")
            .eq("interview_id", interview_id)
            .execute()
        )

    count_result = await asyncio.to_thread(_count_turns)
    turn_count = count_result.count or 0
    if turn_count == 0 or turn_count % SUMMARIZE_EVERY_N_TURNS != 0:
        return

    def _fetch_turns():
        return (
            supabase.table("interview_transcripts")
            .select("speaker, text")
            .eq("interview_id", interview_id)
            .order("turn_index")
            .execute()
        )

    def _fetch_interview():
        return (
            supabase.table("interviews")
            .select("running_summary")
            .eq("id", interview_id)
            .maybe_single()
            .execute()
        )

    turns_result, interview_result = await asyncio.gather(
        asyncio.to_thread(_fetch_turns), asyncio.to_thread(_fetch_interview)
    )

    turns_text = "\n".join(f"{t['speaker']}: {t['text']}" for t in turns_result.data)
    previous_summary = (interview_result.data or {}).get("running_summary") or "none"

    prompt = _SUMMARY_PROMPT.format(previous_summary=previous_summary, turns_text=turns_text)
    summary = await gateway.complete(
        user_id, provider, [Message(role=MessageRole.USER, content=prompt)], _OPTIONS
    )

    def _store():
        return (
            supabase.table("interviews")
            .update({"running_summary": summary.strip()})
            .eq("id", interview_id)
            .execute()
        )

    await asyncio.to_thread(_store)
