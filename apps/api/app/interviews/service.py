import json
import logging
import re
from datetime import UTC, datetime, timedelta

from fastapi import status

from app.core.errors import AppError
from app.db import interviews as interviews_repo
from app.db import resumes as resumes_repo
from app.interviews import summarizer
from app.interviews.orchestrator import is_final_phase, minutes_remaining, phase_for_elapsed
from app.interviews.types import get_config
from app.db.keys import get_key_row
from app.llm import gateway
from app.llm.budget import ensure_user_first, fit_to_budget, truncate
from app.llm.schemas import SetupOut
from app.llm.options import LLMOptions
from app.llm.prompts.interview import (
    SETUP_PROMPT,
    TURN_SYSTEM,
    goal_for,
    question_index_for,
)
from app.providers.base import Message, MessageRole
from app.rag.retrieval import match_question_bank, match_resume_chunks

logger = logging.getLogger(__name__)

MAX_RAW_TURNS_IN_CONTEXT = 6
_OVERRUN_GRACE_MINUTES = 5

_SETUP_OPTIONS = LLMOptions(
    task="interview",
    json_mode=True,
    max_output_tokens=450,
    temperature=0.7,
    feature="interview_setup",
    prompt_id="interview.setup",
    prompt_version="1",
)
# trim_on_length: a reply cut off by the 160-token cap is shown as complete
# sentences, never a dangling half sentence.
_TURN_OPTIONS = LLMOptions(
    task="interview",
    max_output_tokens=160,
    trim_on_length=True,
    feature="interview_turn",
    prompt_id="interview.turn",
    prompt_version="1",
)

_JD_SETUP_TOKENS = 1200
_JD_FALLBACK_TOKENS = 300
_BRIEF_MAX_TOKENS = 300
_RESUME_FALLBACK_TOKENS = 400
_TURN_TOKEN_CAP = 120
_QUESTION_TOKEN_CAP = 400
_PROMPT_BUDGET_TOKENS = 1200


# Thin aliases onto the db layer. Kept as module-level names so the
# orchestration below reads naturally (and tests can replace one step).
_get_owned_interview = interviews_repo.get_owned_interview
_update_interview = interviews_repo.update_interview
_append_transcript = interviews_repo.append_transcript
_next_turn_index = interviews_repo.next_turn_index
_recent_turns = interviews_repo.recent_turns
_get_question_text = interviews_repo.question_text
_create_interview_row = interviews_repo.create_interview


async def _get_owned_processed_resume(user_id: str, resume_id: str) -> dict:
    return await resumes_repo.require_processed_resume(user_id, resume_id, "id, parsed_text, digest")


_OPENING_FIELD = re.compile(r'"opening"\s*:\s*"((?:[^"\\]|\\.)*)')
_FALLBACK_OPENING = "Hello, and thanks for joining. To start, could you tell me a little about yourself?"


def _salvage_opening(raw: str) -> str:
    """The model didn't return usable JSON (e.g. it was cut off by the output
    cap). Never show raw JSON to the candidate: pull the opening text out of
    it if present, otherwise use plain text as-is, otherwise a stock greeting."""
    raw = raw.strip()
    if not raw.startswith(("{", "```")):
        return raw or _FALLBACK_OPENING
    match = _OPENING_FIELD.search(raw)
    if match and match.group(1).strip():
        try:
            return json.loads(f'"{match.group(1)}"').strip()
        except ValueError:
            return match.group(1).strip()
    return _FALLBACK_OPENING


def _elapsed_minutes(interview: dict) -> float:
    started_at = datetime.fromisoformat(interview["started_at"])
    return (datetime.now(UTC) - started_at).total_seconds() / 60


async def start_interview(
    user_id: str, interview_type: str, provider: str, resume_id: str, jd_text: str
) -> dict:
    resume = await _get_owned_processed_resume(user_id, resume_id)

    gemini_key = await get_key_row(user_id, "gemini", "primary")
    if not gemini_key:
        raise AppError(status.HTTP_412_PRECONDITION_FAILED, "key_missing", "A valid primary Gemini key is required to start an interview")

    config = get_config(interview_type)
    interview_id = await _create_interview_row(user_id, interview_type, jd_text, resume_id, provider)

    try:
        jd_embedding = (await gateway.embed(user_id, [jd_text], kind="query"))[0]

        selected_question_ids: list[str] = []
        if config.question_count > 0:
            matches = await match_question_bank(
                interview_type, jd_embedding, match_count=config.question_count
            )
            selected_question_ids = [m["id"] for m in matches]

        resume_context = resume.get("digest")
        if not resume_context:
            relevant_chunks = await match_resume_chunks(resume_id, jd_embedding, match_count=3)
            resume_context = truncate(
                "\n\n".join(c["content"] for c in relevant_chunks)
                or (resume["parsed_text"] or ""),
                _RESUME_FALLBACK_TOKENS,
            )

        setup_prompt = SETUP_PROMPT.format(
            type_line=config.system_prompt,
            goal=goal_for(config.phases[0][0]),
            resume=resume_context,
            jd=truncate(jd_text, _JD_SETUP_TOKENS),
        )
        try:
            setup = await gateway.complete_structured(
                user_id,
                provider,
                [Message(role=MessageRole.USER, content=setup_prompt)],
                SetupOut,
                _SETUP_OPTIONS,
            )
            opening_message, brief = setup.opening, setup.brief
        except gateway.StructuredOutputError as err:
            # The model never produced usable JSON, even after a repair try:
            # use whatever greeting can be salvaged and build the brief
            # without another call.
            opening_message = _salvage_opening(err.raw)
            brief = ""
        if not brief:
            brief = truncate(
                f"{truncate(jd_text, 150)}\nCandidate: {resume_context}", _BRIEF_MAX_TOKENS
            )
        brief = truncate(brief, _BRIEF_MAX_TOKENS)

        now = datetime.now(UTC)
        ends_at = now + timedelta(minutes=config.total_minutes)

        await _update_interview(
            interview_id,
            {
                "status": "in_progress",
                "phase": config.phases[0][0],
                "started_at": now.isoformat(),
                "ends_at": ends_at.isoformat(),
                "selected_question_ids": selected_question_ids,
                "brief": brief,
            },
        )
        await _append_transcript(interview_id, 0, "ai", opening_message)
    except Exception:
        await _update_interview(interview_id, {"status": "aborted"})
        raise

    return await _get_owned_interview(user_id, interview_id)


async def submit_turn(user_id: str, interview_id: str, content: str) -> dict:
    interview = await _get_owned_interview(user_id, interview_id)
    if interview["status"] != "in_progress":
        raise AppError(status.HTTP_409_CONFLICT, "interview_not_active", f"Interview is not in progress (status: {interview['status']})")

    config = get_config(interview["type"])
    elapsed = _elapsed_minutes(interview)
    if elapsed > config.total_minutes + _OVERRUN_GRACE_MINUTES:
        # The time box is fixed: close the interview instead of letting it run on.
        await _update_interview(interview_id, {"status": "completed"})
        raise AppError(status.HTTP_409_CONFLICT, "interview_ended", "This interview's time is up and it has been completed.")
    current_phase = phase_for_elapsed(config, elapsed)
    if current_phase != interview["phase"]:
        await _update_interview(interview_id, {"phase": current_phase})
        interview["phase"] = current_phase

    question_block = ""
    question_ids = interview.get("selected_question_ids") or []
    # Only while a problem is actually being worked on -- not during the intro
    # (which would reveal it early) or the wrap-up.
    if (
        config.needs_coding_platform
        and question_ids
        and (current_phase.startswith("problem_") or current_phase == "coding")
    ):
        index = min(question_index_for(current_phase), len(question_ids) - 1)
        question_text = await _get_question_text(question_ids[index])
        if question_text:
            question_block = (
                f"\nCurrent question: {truncate(question_text, _QUESTION_TOKEN_CAP)}"
            )

    brief = interview.get("brief") or truncate(interview.get("jd_text") or "", _JD_FALLBACK_TOKENS)
    system_text = TURN_SYSTEM.format(
        type_line=config.system_prompt,
        phase=current_phase,
        goal=goal_for(current_phase),
        brief=brief,
        question=question_block,
    )
    messages = [Message(role=MessageRole.SYSTEM, content=system_text)]
    if interview.get("running_summary"):
        messages.append(
            Message(
                role=MessageRole.SYSTEM,
                content=f"Summary of the interview so far: {interview['running_summary']}",
            )
        )
    leading = len(messages)

    # The candidate's new answer goes into the prompt but is only *saved* once
    # the reply succeeded -- otherwise a failed call (429/503) would leave a
    # dangling answer, and the retry would store it twice.
    recent = await _recent_turns(interview_id, MAX_RAW_TURNS_IN_CONTEXT - 1)
    for turn in recent:
        role = MessageRole.ASSISTANT if turn["speaker"] == "ai" else MessageRole.USER
        messages.append(Message(role=role, content=truncate(turn["text"], _TURN_TOKEN_CAP)))
    messages.append(Message(role=MessageRole.USER, content=truncate(content, _TURN_TOKEN_CAP * 4)))
    messages = fit_to_budget(messages, _PROMPT_BUDGET_TOKENS, keep_leading=leading)
    messages = ensure_user_first(messages, leading, placeholder="(interview started)")

    ai_reply = await gateway.complete(user_id, interview["provider"], messages, _TURN_OPTIONS)
    ai_reply = ai_reply.strip()

    turn_index = await _next_turn_index(interview_id)
    await _append_transcript(interview_id, turn_index, "user", content)
    await _append_transcript(interview_id, turn_index + 1, "ai", ai_reply)
    try:
        await summarizer.maybe_update_summary(interview, user_id, interview["provider"])
    except Exception:
        # The reply is already saved and shown; a failed summary (quota, outage)
        # just means it is retried on a later turn -- it must not fail this one.
        logger.warning("Interview summary update failed", exc_info=True)

    return {
        "message": ai_reply,
        "phase": current_phase,
        "minutes_remaining": minutes_remaining(config, elapsed),
        "is_final_phase": is_final_phase(config, current_phase),
    }


async def complete_interview(user_id: str, interview_id: str) -> dict:
    interview = await _get_owned_interview(user_id, interview_id)
    if interview["status"] == "completed":
        return interview
    if interview["status"] != "in_progress":
        raise AppError(status.HTTP_409_CONFLICT, "interview_not_active", f"Only an interview in progress can be completed (status: {interview['status']})")
    await _update_interview(interview_id, {"status": "completed"})
    interview["status"] = "completed"
    return interview


async def get_interview(user_id: str, interview_id: str) -> dict:
    return await _get_owned_interview(user_id, interview_id)


async def list_interviews(user_id: str, limit: int = 50, offset: int = 0) -> list[dict]:
    return await interviews_repo.list_interviews(user_id, limit, offset)


async def get_transcript(user_id: str, interview_id: str) -> list[dict]:
    await _get_owned_interview(user_id, interview_id)
    return await interviews_repo.transcript(interview_id)
