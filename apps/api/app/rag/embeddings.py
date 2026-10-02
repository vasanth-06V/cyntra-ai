from app.llm.budget import truncate
from app.llm.options import Usage
from app.providers.registry import get_adapter

_gemini = get_adapter("gemini")

# gemini-embedding-001 accepts up to 2048 input tokens; stay safely under it
# so one oversized text (a long pasted JD) can't fail a whole batch.
_MAX_INPUT_TOKENS = 1800


async def embed_texts(
    api_key: str, texts: list[str], usage: Usage | None = None, kind: str = "doc"
) -> list[list[float]]:
    """Always Gemini -- the RAG layer routes embeddings through Gemini
    regardless of which provider the user chats with, since it's the only
    one of the three BYOK providers with an embeddings API (Section 6.1).

    The whole list goes out as one batched request (the free tier counts
    requests, not texts: a resume's ~8 chunks or an ATS run's ~20 keywords
    used to cost that many requests each).

    kind="doc" for text that will be searched (resume chunks, bank questions),
    "query" for text used to search with (a JD, a keyword): the model embeds
    the two differently on purpose."""
    prepared = [truncate(t, _MAX_INPUT_TOKENS) for t in texts]
    return await _gemini.embed_many(api_key, prepared, usage=usage, kind=kind)


async def embed_text(api_key: str, text: str) -> list[float]:
    return (await embed_texts(api_key, [text]))[0]
