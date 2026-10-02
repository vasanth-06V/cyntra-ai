from fastapi import status

from app.core.errors import AppError
from app.db import questions as questions_repo
from app.llm import gateway

PERMISSION = "manage_question_bank"


async def _is_owner_or_has_permission(user_id: str, permission: str) -> bool:
    role = await questions_repo.get_role(user_id)
    if role == "owner":
        return True
    if role != "admin":
        return False
    return await questions_repo.has_permission(user_id, permission)


async def _require_permission(user_id: str) -> None:
    if not await _is_owner_or_has_permission(user_id, PERMISSION):
        raise AppError(
            status.HTTP_403_FORBIDDEN, "forbidden", "Not permitted to manage the question bank"
        )


async def _embed_question(user_id: str, question: str) -> list[float]:
    # Raises 412 itself if the user has no Gemini key.
    return (await gateway.embed(user_id, [question]))[0]


async def create_question(
    user_id: str, interview_type: str, question: str, test_cases: list | None, tags: list[str] | None
) -> dict:
    await _require_permission(user_id)
    embedding = await _embed_question(user_id, question)
    return await questions_repo.insert_question(
        {
            "type": interview_type,
            "question": question,
            "test_cases": test_cases,
            "tags": tags or [],
            "embedding": embedding,
            "created_by": user_id,
        }
    )


async def list_questions(
    user_id: str, interview_type: str | None = None, limit: int = 200, offset: int = 0
) -> list[dict]:
    # Test cases are the "answer key"; only people who manage the bank see it.
    await _require_permission(user_id)
    return await questions_repo.list_questions(interview_type, limit, offset)


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

    if not updates:
        raise AppError(status.HTTP_422_UNPROCESSABLE_ENTITY, "validation_failed", "Nothing to update")

    row = await questions_repo.update_question(question_id, updates)
    if not row:
        raise AppError(status.HTTP_404_NOT_FOUND, "not_found", "Question not found")
    return row


async def delete_question(user_id: str, question_id: str) -> None:
    await _require_permission(user_id)
    await questions_repo.delete_question(question_id)
