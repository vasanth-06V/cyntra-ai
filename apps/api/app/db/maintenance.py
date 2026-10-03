"""Bulk reads/writes for the owner-run re-embedding script. Kept in the db
layer like everything else that touches a table."""

from app.core.db import get_supabase
from app.db.base import run


async def stale_chunks(current_version: str, limit: int) -> list[dict]:
    supabase = get_supabase()

    def _q():
        return (
            supabase.table("resume_chunks")
            .select("id, content")
            .neq("embed_version", current_version)
            .limit(limit)
            .execute()
        )

    return (await run(_q)).data or []


async def stale_questions(current_version: str, limit: int) -> list[dict]:
    supabase = get_supabase()

    def _q():
        return (
            supabase.table("question_bank")
            .select("id, type, question, tags, topic")
            .neq("embed_version", current_version)
            .limit(limit)
            .execute()
        )

    return (await run(_q)).data or []


async def set_chunk_embedding(chunk_id: str, embedding: list[float], version: str) -> None:
    supabase = get_supabase()

    def _q():
        return (
            supabase.table("resume_chunks")
            .update({"embedding": embedding, "embed_version": version})
            .eq("id", chunk_id)
            .execute()
        )

    await run(_q)


async def set_question_embedding(question_id: str, embedding: list[float], version: str) -> None:
    supabase = get_supabase()

    def _q():
        return (
            supabase.table("question_bank")
            .update({"embedding": embedding, "embed_version": version})
            .eq("id", question_id)
            .execute()
        )

    await run(_q)


async def all_encrypted_keys() -> list[dict]:
    supabase = get_supabase()

    def _q():
        return supabase.table("provider_keys").select("id, encrypted_key").execute()

    return (await run(_q)).data or []


async def set_encrypted_key(key_id: str, encrypted: str) -> None:
    supabase = get_supabase()

    def _q():
        return supabase.table("provider_keys").update({"encrypted_key": encrypted}).eq("id", key_id).execute()

    await run(_q)
