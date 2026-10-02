from app.core.db import get_supabase
from app.core.errors import AppError
from app.db.base import run


async def get_owned_resume(user_id: str, resume_id: str, columns: str = "id, file_key") -> dict | None:
    supabase = get_supabase()

    def _q():
        return (
            supabase.table("resumes")
            .select(columns)
            .eq("id", resume_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )

    result = await run(_q)
    return result.data if result and result.data else None


async def require_resume(user_id: str, resume_id: str, columns: str = "id, file_key") -> dict:
    row = await get_owned_resume(user_id, resume_id, columns)
    if not row:
        raise AppError(404, "not_found", "Resume not found")
    return row


async def require_processed_resume(user_id: str, resume_id: str, columns: str) -> dict:
    """Owned by the caller AND finished processing (has parsed text)."""
    row = await require_resume(user_id, resume_id, columns)
    if not row.get("parsed_text"):
        raise AppError(422, "resume_not_processed", "This resume hasn't finished processing yet")
    return row


async def replace_chunks_and_finish(
    resume_id: str, chunks: list[dict], parsed_text: str, digest: str | None
) -> None:
    """Replaces the resume's chunks, then marks it processed -- last, so a
    failure partway leaves it unprocessed (retryable), not processed-but-empty."""
    supabase = get_supabase()

    def _q():
        supabase.table("resume_chunks").delete().eq("resume_id", resume_id).execute()
        supabase.table("resume_chunks").insert(chunks).execute()
        supabase.table("resumes").update({"parsed_text": parsed_text, "digest": digest}).eq(
            "id", resume_id
        ).execute()

    await run(_q)


async def match_resume_chunks(
    resume_id: str, query_embedding: list[float], match_count: int = 5
) -> list[dict]:
    supabase = get_supabase()

    def _q():
        return supabase.rpc(
            "match_resume_chunks",
            {
                "query_embedding": query_embedding,
                "filter_resume_id": resume_id,
                "match_count": match_count,
            },
        ).execute()

    return (await run(_q)).data
