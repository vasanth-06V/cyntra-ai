"""The v2 pipeline under evaluation: structure-aware chunker (the scorer changes
in a later M3 step)."""

from app.rag.resume_chunker import chunk_resume

from .harness import EvalChunk, v1_semantic


def chunker(text: str) -> list[EvalChunk]:
    return [EvalChunk(body=c.body, content=c.content, section=c.section) for c in chunk_resume(text)]


semantic = v1_semantic
