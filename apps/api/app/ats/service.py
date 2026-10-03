import logging

from fastapi import HTTPException, status

from app.core.errors import AppError

from app.ats.feedback import generate_feedback
from app.ats.requirements_extractor import extract_requirements
from app.ats.scorer import composite_score, formatting_score, keyword_score, term_present
from app.ats.semantic import Coverage, build_coverage, query_text, semantic_score
from app.db import ats_history
from app.db import resumes as resumes_repo
from app.db.keys import get_key_row
from app.llm import gateway
from app.rag.retrieval import match_resume_chunks_multi

logger = logging.getLogger(__name__)


async def _get_owned_resume(user_id: str, resume_id: str) -> dict:
    return await resumes_repo.require_processed_resume(user_id, resume_id, "id, parsed_text")


async def _coverage(user_id: str, resume_id: str, requirements: dict) -> list[Coverage]:
    """One embedding request for every requirement and ONE database call for
    all their best chunks (it used to be ~20 of each)."""
    terms = requirements["must_have"] + requirements["nice_to_have"]
    queries = [query_text(t) for t in terms]
    embeddings = await gateway.embed(user_id, queries, kind="query")
    rows = await match_resume_chunks_multi(resume_id, embeddings, terms, per_query=1)
    return build_coverage(requirements, rows)


async def score_resume(user_id: str, resume_id: str, provider: str, jd_text: str) -> dict:
    resume = await _get_owned_resume(user_id, resume_id)

    # Fail fast: without a Gemini key the embedding step would fail *after*
    # the extraction call had already spent a request.
    gemini_key = await get_key_row(user_id, "gemini", "primary")
    if not gemini_key:
        raise AppError(status.HTTP_412_PRECONDITION_FAILED, "key_missing", "A valid primary Gemini key is required to score a resume")

    requirements = await extract_requirements(user_id, provider, jd_text)
    if not requirements["must_have"] and not requirements["nice_to_have"]:
        # With nothing to match, every sub-score would be a perfect 1.0.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Couldn't find any skills or requirements in that job description -- paste the full posting.",
        )

    kw_score = keyword_score(requirements, resume["parsed_text"])
    coverage = await _coverage(user_id, resume_id, requirements)
    sem_score = semantic_score(coverage)
    fmt_score = formatting_score(resume["parsed_text"])
    composite = composite_score(kw_score, sem_score, fmt_score)

    # "Missing" means neither the words nor the meaning are there: a skill the
    # resume demonstrates in other words (CI pipelines for "CI/CD") is not missing.
    def _missing(kind: str) -> list[str]:
        return [
            c.term
            for c in coverage
            if c.kind == kind and not c.covered and not term_present(c.term, resume["parsed_text"])
        ]

    missing_must, missing_nice = _missing("must"), _missing("nice")

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

    result = {
        "composite_score": composite,
        "keyword_score": kw_score,
        "semantic_score": sem_score,
        "formatting_score": fmt_score,
        "feedback": feedback,
        "missing_must_have": missing_must,
        "missing_nice_to_have": missing_nice,
        "coverage": [
            {
                "term": c.term,
                "kind": c.kind,
                "covered": c.covered,
                "strength": round(c.strength, 2),
                "section": c.section,
                "evidence": c.evidence,
            }
            for c in coverage
        ],
    }

    # Keep the result so the user can look back (the last 10 per resume). Saving
    # is a convenience: if it fails the score they just earned is still returned.
    try:
        result["history_id"] = await ats_history.record_score(
            user_id,
            resume_id,
            requirements["title"] or None,
            jd_text.strip()[:300],
            provider,
            composite,
            {k: v for k, v in result.items() if k != "history_id"},
        )
    except Exception:
        logger.warning("Could not save the ATS result to history", exc_info=True)
    return result


async def list_history(user_id: str, resume_id: str | None, limit: int, offset: int) -> list[dict]:
    return await ats_history.list_scores(user_id, resume_id, limit, offset)


async def get_history(user_id: str, score_id: str) -> dict:
    row = await ats_history.get_score(user_id, score_id)
    if not row:
        raise AppError(status.HTTP_404_NOT_FOUND, "not_found", "That score was not found.")
    return row


async def delete_history(user_id: str, score_id: str) -> None:
    await ats_history.delete_score(user_id, score_id)
