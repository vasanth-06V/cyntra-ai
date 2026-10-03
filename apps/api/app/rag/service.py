import asyncio
import hashlib
import logging

from fastapi import HTTPException, status

from app.core import background
from app.core.errors import AppError
from app.core.storage import download_bytes
from app.db import resumes as resumes_repo
from app.db.keys import get_key_row
from app.llm import gateway
from app.llm.budget import truncate
from app.llm.models import EMBEDDING_VERSION
from app.llm.options import LLMOptions
from app.llm.prompts.resume import DIGEST_PROMPT
from app.llm.untrusted import NOTICE, new_boundary, sanitize_derived, wrap
from app.providers.base import Message, MessageRole
from app.rag.parsing import extract_text
from app.rag.resume_chunker import CHUNKER_VERSION, chunk_resume

logger = logging.getLogger(__name__)

_DIGEST_OPTIONS = LLMOptions(
    task="extract",
    max_output_tokens=300,
    temperature=0.2,
    feature="resume_digest",
    priority="background",
    prompt_id="resume.digest",
    prompt_version="1",
)
_DIGEST_INPUT_TOKENS = 1500
_DIGEST_MAX_TOKENS = 300
_MAX_FILE_BYTES = 500 * 1024  # keep equal to the web upload limit
_MAX_CHUNKS = 60  # keeps embedding to a single batched request
_MAX_TEXT_CHARS = 40_000  # ~10 pages of dense text; a resume is far shorter


def content_hash(text: str) -> str:
    """Identifies "this exact text, chunked and embedded this way". If it is
    unchanged, re-processing the resume would spend embedding quota for
    nothing."""
    return hashlib.sha256(f"{CHUNKER_VERSION}|{EMBEDDING_VERSION}|{text}".encode()).hexdigest()


async def _make_digest(user_id: str, text: str) -> str | None:
    """One short call that distills the resume for later interviews. Optional:
    a failure here must never fail resume processing."""
    try:
        prompt = DIGEST_PROMPT.format(
            notice=NOTICE,
            resume_text=wrap("resume", truncate(text, _DIGEST_INPUT_TOKENS), new_boundary()),
        )
        digest = await gateway.complete(
            user_id, "gemini", [Message(role=MessageRole.USER, content=prompt)], _DIGEST_OPTIONS
        )
        # Distilled from the resume and stored for every later interview: sanitize it.
        return sanitize_derived(digest, _DIGEST_MAX_TOKENS) or None
    except Exception:
        logger.warning("Resume digest failed; continuing without it", exc_info=True)
        return None


async def _store_digest(user_id: str, resume_id: str, text: str) -> None:
    digest = await _make_digest(user_id, text)
    if digest:
        await resumes_repo.set_digest(resume_id, digest)


async def _get_owned_resume(user_id: str, resume_id: str) -> dict:
    return await resumes_repo.require_resume(
        user_id, resume_id, "id, file_key, parsed_text, content_hash, digest"
    )


async def process_resume(user_id: str, resume_id: str) -> int:
    """Downloads the resume from object storage, extracts text, chunks it into labelled
    sections, embeds the chunks (always via Gemini -- see rag/embeddings.py)
    and stores them atomically. Returns the number of chunks. Re-processing an
    unchanged resume costs no embedding quota."""
    resume = await _get_owned_resume(user_id, resume_id)

    gemini_key = await get_key_row(user_id, "gemini", "primary")
    if not gemini_key:
        raise AppError(status.HTTP_412_PRECONDITION_FAILED, "key_missing", "A valid primary Gemini key is required to process a resume")

    # The backend reads with storage credentials that can see every user's files,
    # so a key written by a client must never be trusted to point anywhere else.
    file_key = str(resume["file_key"])
    if not file_key.startswith(f"resumes/{user_id}/") or ".." in file_key:
        raise AppError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "invalid_file",
            "This resume's file reference is not valid -- please upload it again.",
        )
    try:
        file_bytes = await asyncio.to_thread(download_bytes, file_key)
    except Exception as exc:
        # Providers differ: R2/S3 send code NoSuchKey, Supabase Storage sends a
        # bare 404 with an empty code -- so look at the HTTP status too.
        http_status = getattr(exc, "response", {}).get("ResponseMetadata", {}).get("HTTPStatusCode")
        missing = http_status == 404 or "NoSuchKey" in repr(exc)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND if missing else status.HTTP_502_BAD_GATEWAY,
            detail="The uploaded file could not be found -- please upload it again."
            if missing
            else "Couldn't fetch the file from storage right now -- please retry.",
        ) from exc
    if len(file_bytes) > _MAX_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This file is too large to process (max 500KB).",
        )
    try:
        text = (await asyncio.to_thread(extract_text, file_key, file_bytes))[:_MAX_TEXT_CHARS]
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Couldn't read this file -- is it a valid PDF or DOCX?",
        ) from exc

    digest_hash = content_hash(text)
    if resume.get("content_hash") == digest_hash and resume.get("parsed_text"):
        existing = await resumes_repo.chunk_count(resume_id)
        if existing:
            return existing  # identical content already chunked and embedded this way

    chunks = chunk_resume(text)
    if not chunks:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No extractable text found in this file",
        )
    if len(chunks) > _MAX_CHUNKS:
        logger.warning("Resume has %d chunks; keeping the first %d", len(chunks), _MAX_CHUNKS)
        chunks = chunks[:_MAX_CHUNKS]

    # Documents are embedded with their section header ("Experience | role")
    # so each chunk carries its own context.
    embeddings = await gateway.embed(user_id, [c.content for c in chunks], kind="doc")

    rows = [
        {"chunk_index": i, "content": c.content, "section": c.section, "embedding": embedding}
        for i, (c, embedding) in enumerate(zip(chunks, embeddings))
    ]
    count = await resumes_repo.replace_chunks(
        user_id, resume_id, text, digest_hash, EMBEDDING_VERSION, rows
    )

    # The digest only speeds up later interviews (they fall back to the chunks
    # without it), so it is made after the resume is already usable.
    background.schedule(
        _store_digest(user_id, resume_id, text),
        name=f"digest:{resume_id}",
        key=f"digest:{resume_id}",
    )
    return count
