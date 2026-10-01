import asyncio

from app.providers.registry import get_adapter

_gemini = get_adapter("gemini")


async def embed_text(api_key: str, text: str) -> list[float]:
    """Always Gemini -- the RAG layer routes embeddings through Gemini
    regardless of which provider the user chats with, since it's the only
    one of the three BYOK providers with an embeddings API (Section 6.1)."""
    return await _gemini.embed(api_key, text)


async def embed_chunks(api_key: str, chunks: list[str]) -> list[list[float]]:
    return list(await asyncio.gather(*(embed_text(api_key, c) for c in chunks)))
