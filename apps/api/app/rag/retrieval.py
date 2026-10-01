import asyncio

from app.core.db import get_supabase


async def match_resume_chunks(
    resume_id: str, query_embedding: list[float], match_count: int = 5
) -> list[dict]:
    supabase = get_supabase()

    def _query():
        return supabase.rpc(
            "match_resume_chunks",
            {
                "query_embedding": query_embedding,
                "filter_resume_id": resume_id,
                "match_count": match_count,
            },
        ).execute()

    result = await asyncio.to_thread(_query)
    return result.data


async def match_question_bank(
    interview_type: str, query_embedding: list[float], match_count: int = 2
) -> list[dict]:
    supabase = get_supabase()

    def _query():
        return supabase.rpc(
            "match_question_bank",
            {
                "query_embedding": query_embedding,
                "filter_type": interview_type,
                "match_count": match_count,
            },
        ).execute()

    result = await asyncio.to_thread(_query)
    return result.data
