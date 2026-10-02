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


async def replace_chunks(
    user_id: str,
    resume_id: str,
    parsed_text: str,
    content_hash: str,
    embed_version: str,
    chunks: list[dict],
) -> int:
    """Replaces the resume's chunks and marks it processed in ONE database
    transaction (rpc replace_resume_chunks), under a row lock: a failure leaves
    the previous state intact and two concurrent runs cannot interleave."""
    supabase = get_supabase()

    def _q():
        return supabase.rpc(
            "replace_resume_chunks",
            {
                "p_resume_id": resume_id,
                "p_user_id": user_id,
                "p_text": parsed_text,
                "p_content_hash": content_hash,
                "p_embed_version": embed_version,
                "p_chunks": chunks,
            },
        ).execute()

    return int((await run(_q)).data or 0)


async def chunk_count(resume_id: str) -> int:
    supabase = get_supabase()

    def _q():
        return (
            supabase.table("resume_chunks")
            .select("id", count="exact")
            .eq("resume_id", resume_id)
            .execute()
        )

    return (await run(_q)).count or 0


async def set_digest(resume_id: str, digest: str) -> None:
    supabase = get_supabase()

    def _q():
        return supabase.table("resumes").update({"digest": digest}).eq("id", resume_id).execute()

    await run(_q)


async def match_resume_chunks_multi(
    resume_id: str, embeddings: list[list[float]], terms: list[str], per_query: int = 1
) -> list[dict]:
    """The best chunk(s) for every requirement in ONE call. Each row says which
    requirement it answers (q_idx), how similar the chunk is, whether the
    chunk itself contains the term (kw_hit) and whether any chunk of the
    resume does (kw_any)."""
    supabase = get_supabase()

    def _q():
        return supabase.rpc(
            "match_resume_chunks_multi",
            {
                "filter_resume_id": resume_id,
                "query_embeddings": embeddings,
                "query_terms": terms,
                "per_query": per_query,
            },
        ).execute()

    return (await run(_q)).data or []
