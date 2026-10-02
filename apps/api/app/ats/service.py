import asyncio

from fastapi import HTTPException, status

from app.ats.feedback import generate_feedback
from app.ats.requirements_extractor import extract_requirements
from app.ats.scorer import composite_score, formatting_score, keyword_score, missing_terms
from app.core.db import get_supabase
from app.keys.service import get_key_row
from app.llm import gateway
from app.rag.retrieval import match_resume_chunks


async def _get_owned_resume(user_id: str, resume_id: str) -> dict:
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


async def _semantic_score(user_id: str, resume_id: str, requirements: dict) -> float:
    terms = requirements["must_have"] + requirements["nice_to_have"]
    if not terms:
        return 1.0

    # One embedding request for every keyword (was one per keyword, ~20 per
    # run). The per-keyword resume lookups are plain DB queries -- no model
    # quota -- so they run concurrently.
    embeddings = await gateway.embed(user_id, terms)
    matches = await asyncio.gather(
        *(match_resume_chunks(resume_id, e, match_count=1) for e in embeddings)
    )
    similarities = [max(0.0, m[0]["similarity"]) if m else 0.0 for m in matches]
    return sum(similarities) / len(similarities)


async def score_resume(user_id: str, resume_id: str, provider: str, jd_text: str) -> dict:
    resume = await _get_owned_resume(user_id, resume_id)

    # Fail fast: without a Gemini key the embedding step would fail *after*
    # the extraction call had already spent a request.
    gemini_key = await get_key_row(user_id, "gemini", "primary")
    if not gemini_key:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="A valid primary Gemini key is required to score a resume",
        )

    requirements = await extract_requirements(user_id, provider, jd_text)
    if not requirements["must_have"] and not requirements["nice_to_have"]:
        # With nothing to match, every sub-score would be a perfect 1.0.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Couldn't find any skills or requirements in that job description -- paste the full posting.",
        )

    kw_score = keyword_score(requirements, resume["parsed_text"])
    sem_score = await _semantic_score(user_id, resume_id, requirements)
    fmt_score = formatting_score(resume["parsed_text"])
    composite = composite_score(kw_score, sem_score, fmt_score)
    missing_must, missing_nice = missing_terms(requirements, resume["parsed_text"])

    feedback = await generate_feedback(
        user_id,
        provider,
        requirements["title"],
        missing_must,
        missing_nice,
        kw_score,
        sem_score,
        fmt_score,
    )

    return {
        "composite_score": composite,
        "keyword_score": kw_score,
        "semantic_score": sem_score,
        "formatting_score": fmt_score,
        "feedback": feedback,
        "missing_must_have": missing_must,
        "missing_nice_to_have": missing_nice,
    }
