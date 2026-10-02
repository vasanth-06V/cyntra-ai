import asyncio
import logging

from fastapi import HTTPException, status

from app.core.db import get_supabase
from app.core.storage import download_bytes
from app.keys.service import get_key_row
from app.rag.chunking import chunk_text
from app.llm import gateway
from app.llm.budget import truncate
from app.llm.options import LLMOptions
from app.llm.prompts.resume import DIGEST_PROMPT
from app.providers.base import Message, MessageRole
from app.rag.parsing import extract_text

logger = logging.getLogger(__name__)

_DIGEST_OPTIONS = LLMOptions(task="extract", max_output_tokens=300, temperature=0.2)
_DIGEST_INPUT_TOKENS = 1500


async def _make_digest(user_id: str, text: str) -> str | None:
    """One short call that distills the resume for later interviews. Optional:
    a failure here must never fail resume processing."""
    try:
        prompt = DIGEST_PROMPT.format(resume_text=truncate(text, _DIGEST_INPUT_TOKENS))
        digest = await gateway.complete(
            user_id, "gemini", [Message(role=MessageRole.USER, content=prompt)], _DIGEST_OPTIONS
        )
        return digest.strip() or None
    except Exception:
        logger.warning("Resume digest failed; continuing without it", exc_info=True)
        return None


async def _get_owned_resume(user_id: str, resume_id: str) -> dict:
    supabase = get_supabase()

    def _query():
        return (
            supabase.table("resumes")
            .select("id, file_key")
            .eq("id", resume_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )

    result = await asyncio.to_thread(_query)
    if not result or not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
    return result.data


async def process_resume(user_id: str, resume_id: str) -> int:
    """Downloads the resume from R2, extracts text, chunks it, embeds each
    chunk (always via Gemini -- see rag/embeddings.py), and stores the
    result. Returns the number of chunks created."""
    resume = await _get_owned_resume(user_id, resume_id)

    gemini_key = await get_key_row(user_id, "gemini", "primary")
    if not gemini_key:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="A valid primary Gemini key is required to process a resume",
        )

    file_bytes = await asyncio.to_thread(download_bytes, resume["file_key"])
    text = await asyncio.to_thread(extract_text, resume["file_key"], file_bytes)
    chunks = chunk_text(text)

    if not chunks:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No extractable text found in this file",
        )

    embeddings = await gateway.embed(user_id, chunks)

    digest = await _make_digest(user_id, text)

    supabase = get_supabase()

    def _store():
        supabase.table("resumes").update({"parsed_text": text, "digest": digest}).eq("id", resume_id).execute()
        supabase.table("resume_chunks").delete().eq("resume_id", resume_id).execute()
        supabase.table("resume_chunks").insert(
            [
                {
                    "resume_id": resume_id,
                    "chunk_index": i,
                    "content": chunk,
                    "embedding": embedding,
                }
                for i, (chunk, embedding) in enumerate(zip(chunks, embeddings))
            ]
        ).execute()

    await asyncio.to_thread(_store)
    return len(chunks)
