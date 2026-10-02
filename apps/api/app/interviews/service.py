import asyncio
import json
import logging
import re
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status

from app.core.db import get_supabase
from app.interviews import summarizer
from app.interviews.orchestrator import is_final_phase, minutes_remaining, phase_for_elapsed
from app.interviews.types import get_config
from app.keys.service import get_key_row
from app.llm import gateway
from app.llm.budget import ensure_user_first, fit_to_budget, truncate
from app.llm.json_utils import extract_json
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

_SETUP_OPTIONS = LLMOptions(
    task="interview", json_mode=True, max_output_tokens=450, temperature=0.7
)
_TURN_OPTIONS = LLMOptions(task="interview", max_output_tokens=160)

_JD_SETUP_TOKENS = 1200
_JD_FALLBACK_TOKENS = 300
_BRIEF_MAX_TOKENS = 300
_RESUME_FALLBACK_TOKENS = 400
_TURN_TOKEN_CAP = 120
_QUESTION_TOKEN_CAP = 400
_PROMPT_BUDGET_TOKENS = 1200


async def _get_owned_processed_resume(user_id: str, resume_id: str) -> dict:
    supabase = get_supabase()

    def _query():
        return (
            supabase.table("resumes")
            .select("id, parsed_text, digest")
            .eq("id", resume_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )

    result = await asyncio.to_thread(_query)
    if not result or not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
    if not result.data.get("parsed_text"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This resume hasn't finished processing yet",
        )
    return result.data


async def _get_owned_interview(user_id: str, interview_id: str) -> dict:
    supabase = get_supabase()

    def _query():
        return (
            supabase.table("interviews")
            .select("*")
            .eq("id", interview_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )

    result = await asyncio.to_thread(_query)
    if not result or not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found")
    return result.data


async def _create_interview_row(
    user_id: str, interview_type: str, jd_text: str, resume_id: str, provider: str
) -> str:
    supabase = get_supabase()

    def _insert():
        return (
            supabase.table("interviews")
            .insert(
                {
                    "user_id": user_id,
                    "type": interview_type,
                    "jd_text": jd_text,
                    "resume_id": resume_id,
                    "provider": provider,
                    "status": "setting_up",
                }
            )
            .execute()
        )

    result = await asyncio.to_thread(_insert)
    return result.data[0]["id"]


async def _update_interview(interview_id: str, fields: dict) -> None:
    supabase = get_supabase()

    def _update():
        return supabase.table("interviews").update(fields).eq("id", interview_id).execute()

    await asyncio.to_thread(_update)


async def _append_transcript(interview_id: str, turn_index: int, speaker: str, text: str) -> None:
    supabase = get_supabase()

    def _insert():
        return (
            supabase.table("interview_transcripts")
            .insert(
                {
                    "interview_id": interview_id,
                    "turn_index": turn_index,
                    "speaker": speaker,
                    "text": text,
                }
            )
            .execute()
        )

    await asyncio.to_thread(_insert)


async def _next_turn_index(interview_id: str) -> int:
    supabase = get_supabase()

    def _query():
        return (
            supabase.table("interview_transcripts")
            .select("turn_index")
            .eq("interview_id", interview_id)
            .order("turn_index", desc=True)
            .limit(1)
            .execute()
        )

    result = await asyncio.to_thread(_query)
    return (result.data[0]["turn_index"] + 1) if result.data else 0


async def _recent_turns(interview_id: str, limit: int) -> list[dict]:
    supabase = get_supabase()

    def _query():
        return (
            supabase.table("interview_transcripts")
            .select("speaker, text")
            .eq("interview_id", interview_id)
            .order("turn_index", desc=True)
            .limit(limit)
            .execute()
        )

    result = await asyncio.to_thread(_query)
    return list(reversed(result.data))


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


async def _get_question_text(question_id: str) -> str | None:
    supabase = get_supabase()

    def _query():
        return (
            supabase.table("question_bank")
            .select("question")
            .eq("id", question_id)
            .maybe_single()
            .execute()
        )

    result = await asyncio.to_thread(_query)
    return (result.data or {}).get("question") if result else None


def _elapsed_minutes(interview: dict) -> float:
    started_at = datetime.fromisoformat(interview["started_at"])
    return (datetime.now(UTC) - started_at).total_seconds() / 60


async def start_interview(
    user_id: str, interview_type: str, provider: str, resume_id: str, jd_text: str
) -> dict:
    resume = await _get_owned_processed_resume(user_id, resume_id)

    gemini_key = await get_key_row(user_id, "gemini", "primary")
    if not gemini_key:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="A valid primary Gemini key is required to start an interview",
        )

    config = get_config(interview_type)
    interview_id = await _create_interview_row(user_id, interview_type, jd_text, resume_id, provider)

    try:
        jd_embedding = (await gateway.embed(user_id, [jd_text]))[0]

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
        raw = await gateway.complete(
            user_id,
            provider,
            [Message(role=MessageRole.USER, content=setup_prompt)],
            _SETUP_OPTIONS,
        )
        try:
            data = extract_json(raw)
            opening_message = str(data["opening"]).strip()
            brief = str(data.get("brief") or "").strip()
            if not opening_message:
                raise ValueError("empty opening")
        except (ValueError, KeyError, TypeError):
            # The model ignored the format: use its text as the greeting and
            # build the brief without another call.
            opening_message = _salvage_opening(raw)
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
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Interview is not in progress (status: {interview['status']})",
        )

    config = get_config(interview["type"])
    elapsed = _elapsed_minutes(interview)
    current_phase = phase_for_elapsed(config, elapsed)
    if current_phase != interview["phase"]:
        await _update_interview(interview_id, {"phase": current_phase})
        interview["phase"] = current_phase

    turn_index = await _next_turn_index(interview_id)
    await _append_transcript(interview_id, turn_index, "user", content)

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

    recent = await _recent_turns(interview_id, MAX_RAW_TURNS_IN_CONTEXT)
    for turn in recent:
        role = MessageRole.ASSISTANT if turn["speaker"] == "ai" else MessageRole.USER
        messages.append(Message(role=role, content=truncate(turn["text"], _TURN_TOKEN_CAP)))
    messages = fit_to_budget(messages, _PROMPT_BUDGET_TOKENS, keep_leading=leading)
    messages = ensure_user_first(messages, leading, placeholder="(interview started)")

    ai_reply = await gateway.complete(user_id, interview["provider"], messages, _TURN_OPTIONS)
    ai_reply = ai_reply.strip()

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
    await _update_interview(interview_id, {"status": "completed"})
    interview["status"] = "completed"
    return interview


async def get_interview(user_id: str, interview_id: str) -> dict:
    return await _get_owned_interview(user_id, interview_id)


async def list_interviews(user_id: str) -> list[dict]:
    supabase = get_supabase()

    def _query():
        return (
            supabase.table("interviews")
            .select("id, type, status, phase, provider, resume_id, started_at, ends_at, created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )

    result = await asyncio.to_thread(_query)
    return result.data


async def get_transcript(user_id: str, interview_id: str) -> list[dict]:
    await _get_owned_interview(user_id, interview_id)
    supabase = get_supabase()

    def _query():
        return (
            supabase.table("interview_transcripts")
            .select("id, turn_index, speaker, text, created_at")
            .eq("interview_id", interview_id)
            .order("turn_index")
            .execute()
        )

    result = await asyncio.to_thread(_query)
    return result.data
