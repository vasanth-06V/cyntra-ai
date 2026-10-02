from app.db import interviews as interviews_repo
from app.llm import gateway
from app.llm.budget import truncate
from app.llm.options import LLMOptions
from app.llm.prompts.interview import SUMMARY_PROMPT
from app.llm.untrusted import NOTICE, new_boundary, sanitize_derived, wrap
from app.providers.base import Message, MessageRole

_OPTIONS = LLMOptions(
    task="summarize",
    max_output_tokens=150,
    temperature=0.2,
    feature="interview_summary",
    priority="background",
    prompt_id="interview.summary",
    prompt_version="2",
)

SUMMARIZE_EVERY_N_TURNS = 8
_TURN_TOKEN_CAP = 150
_SUMMARY_MAX_TOKENS = 150


async def maybe_update_summary(interview: dict, user_id: str, provider: str) -> None:
    """Keeps token usage flat as an interview gets long: once
    SUMMARIZE_EVERY_N_TURNS turns have piled up since the last summary, fold
    only those new turns into the running summary (never the whole
    transcript again). `interview` is the row already loaded by the caller."""
    interview_id = interview["id"]
    through = interview.get("summarized_through_turn") or 0

    turns = await interviews_repo.turns_since(interview_id, through)
    if len(turns) < SUMMARIZE_EVERY_N_TURNS:
        return

    boundary = new_boundary()
    # Candidate turns are untrusted; the interviewer's own replies are ours.
    turns_text = "\n".join(
        f"{t['speaker']}: "
        + (
            truncate(t["text"], _TURN_TOKEN_CAP)
            if t["speaker"] == "ai"
            else wrap("candidate_answer", truncate(t["text"], _TURN_TOKEN_CAP), boundary)
        )
        for t in turns
    )
    previous = interview.get("running_summary")
    prompt = SUMMARY_PROMPT.format(
        notice=NOTICE,
        previous=wrap("interview_summary", previous, boundary) if previous else "none",
        turns=turns_text,
    )
    summary = await gateway.complete(
        user_id, provider, [Message(role=MessageRole.USER, content=prompt)], _OPTIONS
    )

    await interviews_repo.update_interview(
        interview_id,
        {
            # Distilled from candidate text and re-used later: sanitize and cap it.
            "running_summary": sanitize_derived(summary, _SUMMARY_MAX_TOKENS),
            "summarized_through_turn": turns[-1]["turn_index"] + 1,
        },
    )
