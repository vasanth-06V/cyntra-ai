import asyncio

from fastapi import HTTPException, status

from app.core.db import get_supabase
from app.core.security import decrypt_key
from app.keys.service import get_key_row
from app.rag.embeddings import embed_text

PERMISSION = "manage_question_bank"


async def _is_owner_or_has_permission(user_id: str, permission: str) -> bool:
    supabase = get_supabase()

    def _query_role():
        return (
            supabase.table("roles")
            .select("role")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )

    role_result = await asyncio.to_thread(_query_role)
    role = role_result.data["role"] if role_result and role_result.data else None
    if role == "owner":
        return True
    if role != "admin":
        return False

    def _query_permission():
        return (
            supabase.table("admin_permissions")
            .select("id")
            .eq("admin_id", user_id)
            .eq("permission_key", permission)
            .maybe_single()
            .execute()
        )

    perm_result = await asyncio.to_thread(_query_permission)
    return bool(perm_result and perm_result.data)


async def _require_permission(user_id: str) -> None:
    if not await _is_owner_or_has_permission(user_id, PERMISSION):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not permitted to manage the question bank",
        )


async def _embed_question(user_id: str, question: str) -> list[float]:
    gemini_key = await get_key_row(user_id, "gemini", "primary")
    if not gemini_key:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="A valid primary Gemini key is required to save a question",
        )
    return await embed_text(decrypt_key(gemini_key["encrypted_key"]), question)


async def create_question(
    user_id: str, interview_type: str, question: str, test_cases: list | None, tags: list[str] | None
) -> dict:
    await _require_permission(user_id)
    embedding = await _embed_question(user_id, question)

    supabase = get_supabase()

    def _insert():
        return (
            supabase.table("question_bank")
            .insert(
                {
                    "type": interview_type,
                    "question": question,
                    "test_cases": test_cases,
                    "tags": tags or [],
                    "embedding": embedding,
                    "created_by": user_id,
                }
            )
            .execute()
        )

    result = await asyncio.to_thread(_insert)
    return result.data[0]


async def list_questions(interview_type: str | None = None) -> list[dict]:
    supabase = get_supabase()

    def _query():
        q = supabase.table("question_bank").select(
            "id, type, question, test_cases, tags, created_by, created_at"
        )
        if interview_type:
            q = q.eq("type", interview_type)
        return q.order("created_at", desc=True).execute()

    result = await asyncio.to_thread(_query)
    return result.data


async def update_question(
    user_id: str,
    question_id: str,
    question: str | None,
    test_cases: list | None,
    tags: list[str] | None,
) -> dict:
    await _require_permission(user_id)

    updates: dict = {}
    if question is not None:
        updates["question"] = question
        updates["embedding"] = await _embed_question(user_id, question)
    if test_cases is not None:
        updates["test_cases"] = test_cases
    if tags is not None:
        updates["tags"] = tags

    supabase = get_supabase()

    def _update():
        return (
            supabase.table("question_bank").update(updates).eq("id", question_id).execute()
        )

    result = await asyncio.to_thread(_update)
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    return result.data[0]


async def delete_question(user_id: str, question_id: str) -> None:
    await _require_permission(user_id)
    supabase = get_supabase()

    def _delete():
        return supabase.table("question_bank").delete().eq("id", question_id).execute()

    await asyncio.to_thread(_delete)
