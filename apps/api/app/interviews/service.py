import asyncio
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status

from app.core.db import get_supabase
from app.interviews import summarizer
from app.interviews.orchestrator import is_final_phase, minutes_remaining, phase_for_elapsed
from app.interviews.types import get_config
from app.keys.service import get_key_row
from app.llm import gateway
from app.llm.options import LLMOptions
from app.providers.base import Message, MessageRole
from app.rag.retrieval import match_question_bank, match_resume_chunks

MAX_RAW_TURNS_IN_CONTEXT = 8

_OPENING_OPTIONS = LLMOptions(task="interview", max_output_tokens=250)
_TURN_OPTIONS = LLMOptions(task="interview", max_output_tokens=200)


async def _get_owned_processed_resume(user_id: str, resume_id: str) -> dict:
    supabase = get_supabase()

    def _query():
        return (
            supabase.table("resumes")
            .select("id, parsed_text")
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

        relevant_chunks = await match_resume_chunks(resume_id, jd_embedding, match_count=3)
        resume_context = (
            "\n\n".join(c["content"] for c in relevant_chunks)
            or (resume["parsed_text"] or "")[:2000]
        )

        opening_prompt = (
            f"{config.system_prompt}\n\n"
            f"Candidate's relevant resume context:\n{resume_context}\n\n"
            f"Job description:\n{jd_text}\n\n"
            "Write a brief, friendly opening greeting (2-3 sentences) introducing "
            "yourself as the interviewer and asking your first question for the "
            "opening phase. Respond with only what you would say out loud -- no "
            "labels, no stage directions."
        )
        opening_message = await gateway.complete(
            user_id,
            provider,
            [Message(role=MessageRole.USER, content=opening_prompt)],
            _OPENING_OPTIONS,
        )

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
            },
        )
        await _append_transcript(interview_id, 0, "ai", opening_message.strip())
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

    resume = await _get_owned_processed_resume(user_id, interview["resume_id"])
    system_text = (
        f"{config.system_prompt}\n\n"
        f"Job description:\n{interview['jd_text']}\n\n"
        f"Current interview phase: {current_phase}."
    )
    messages = [Message(role=MessageRole.SYSTEM, content=system_text)]
    if interview.get("running_summary"):
        messages.append(
            Message(
                role=MessageRole.SYSTEM,
                content=f"Summary of the interview so far: {interview['running_summary']}",
            )
        )

    recent = await _recent_turns(interview_id, MAX_RAW_TURNS_IN_CONTEXT)
    for turn in recent:
        role = MessageRole.ASSISTANT if turn["speaker"] == "ai" else MessageRole.USER
        messages.append(Message(role=role, content=turn["text"]))

    ai_reply = await gateway.complete(user_id, interview["provider"], messages, _TURN_OPTIONS)
    ai_reply = ai_reply.strip()

    await _append_transcript(interview_id, turn_index + 1, "ai", ai_reply)
    await summarizer.maybe_update_summary(interview_id, user_id, interview["provider"])

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
