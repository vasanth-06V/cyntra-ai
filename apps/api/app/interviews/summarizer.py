import asyncio

from app.core.db import get_supabase
from app.llm import gateway
from app.llm.budget import truncate
from app.llm.options import LLMOptions
from app.llm.prompts.interview import SUMMARY_PROMPT
from app.providers.base import Message, MessageRole

_OPTIONS = LLMOptions(task="summarize", max_output_tokens=150, temperature=0.2)

SUMMARIZE_EVERY_N_TURNS = 8
_TURN_TOKEN_CAP = 150


async def maybe_update_summary(interview: dict, user_id: str, provider: str) -> None:
    """Keeps token usage flat as an interview gets long: once
    SUMMARIZE_EVERY_N_TURNS turns have piled up since the last summary, fold
    only those new turns into the running summary (never the whole
    transcript again). `interview` is the row already loaded by the caller."""
    interview_id = interview["id"]
    through = interview.get("summarized_through_turn") or 0
    supabase = get_supabase()

    def _fetch_new_turns():
        return (
            supabase.table("interview_transcripts")
            .select("turn_index, speaker, text")
            .eq("interview_id", interview_id)
            .gte("turn_index", through)
            .order("turn_index")
            .execute()
        )

    result = await asyncio.to_thread(_fetch_new_turns)
    turns = result.data or []
    if len(turns) < SUMMARIZE_EVERY_N_TURNS:
        return

    turns_text = "\n".join(
        f"{t['speaker']}: {truncate(t['text'], _TURN_TOKEN_CAP)}" for t in turns
    )
    prompt = SUMMARY_PROMPT.format(
        previous=interview.get("running_summary") or "none", turns=turns_text
    )
    summary = await gateway.complete(
        user_id, provider, [Message(role=MessageRole.USER, content=prompt)], _OPTIONS
    )

    fields = {
        "running_summary": summary.strip(),
        "summarized_through_turn": turns[-1]["turn_index"] + 1,
    }

    def _store():
        return supabase.table("interviews").update(fields).eq("id", interview_id).execute()

    await asyncio.to_thread(_store)
