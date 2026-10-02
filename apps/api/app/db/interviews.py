from app.core.db import get_supabase
from app.core.errors import AppError
from app.db.base import run


async def get_owned_interview(user_id: str, interview_id: str) -> dict:
    supabase = get_supabase()

    def _q():
        return (
            supabase.table("interviews")
            .select("*")
            .eq("id", interview_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )

    result = await run(_q)
    if not result or not result.data:
        raise AppError(404, "not_found", "Interview not found")
    return result.data


async def create_interview(
    user_id: str, interview_type: str, jd_text: str, resume_id: str, provider: str
) -> str:
    supabase = get_supabase()

    def _q():
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

    return (await run(_q)).data[0]["id"]


async def update_interview(interview_id: str, fields: dict) -> None:
    supabase = get_supabase()

    def _q():
        return supabase.table("interviews").update(fields).eq("id", interview_id).execute()

    await run(_q)


async def list_interviews(user_id: str, limit: int = 50, offset: int = 0) -> list[dict]:
    supabase = get_supabase()

    def _q():
        return (
            supabase.table("interviews")
            .select("id, type, status, phase, provider, resume_id, started_at, ends_at, created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )

    return (await run(_q)).data


async def append_transcript(interview_id: str, turn_index: int, speaker: str, text: str) -> None:
    supabase = get_supabase()

    def _q():
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

    await run(_q)


async def next_turn_index(interview_id: str) -> int:
    supabase = get_supabase()

    def _q():
        return (
            supabase.table("interview_transcripts")
            .select("turn_index")
            .eq("interview_id", interview_id)
            .order("turn_index", desc=True)
            .limit(1)
            .execute()
        )

    result = await run(_q)
    return (result.data[0]["turn_index"] + 1) if result.data else 0


async def recent_turns(interview_id: str, limit: int) -> list[dict]:
    supabase = get_supabase()

    def _q():
        return (
            supabase.table("interview_transcripts")
            .select("speaker, text")
            .eq("interview_id", interview_id)
            .order("turn_index", desc=True)
            .limit(limit)
            .execute()
        )

    return list(reversed((await run(_q)).data))


async def transcript(interview_id: str) -> list[dict]:
    supabase = get_supabase()

    def _q():
        return (
            supabase.table("interview_transcripts")
            .select("id, turn_index, speaker, text, created_at")
            .eq("interview_id", interview_id)
            .order("turn_index")
            .execute()
        )

    return (await run(_q)).data


async def turns_since(interview_id: str, from_turn: int) -> list[dict]:
    supabase = get_supabase()

    def _q():
        return (
            supabase.table("interview_transcripts")
            .select("turn_index, speaker, text")
            .eq("interview_id", interview_id)
            .gte("turn_index", from_turn)
            .order("turn_index")
            .execute()
        )

    return (await run(_q)).data or []


async def asked_question_ids(user_id: str, limit: int = 100) -> list[str]:
    """Question ids from the user's recent interviews, so a new interview can
    avoid repeating them."""
    supabase = get_supabase()

    def _q():
        return (
            supabase.table("interviews")
            .select("selected_question_ids")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )

    seen: dict[str, None] = {}
    for row in (await run(_q)).data or []:
        for qid in row.get("selected_question_ids") or []:
            seen[qid] = None
    return list(seen)


async def question_text(question_id: str) -> str | None:
    supabase = get_supabase()

    def _q():
        return (
            supabase.table("question_bank")
            .select("question")
            .eq("id", question_id)
            .maybe_single()
            .execute()
        )

    result = await run(_q)
    return (result.data or {}).get("question") if result else None
