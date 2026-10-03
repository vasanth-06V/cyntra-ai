from fastapi import status

from app.core.errors import AppError
from app.db import questions as questions_repo
from app.llm import gateway
from app.interviews.types import get_config
from app.llm.models import EMBEDDING_VERSION

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


def embedding_text(interview_type: str, question: str, topic: str | None, tags: list[str] | None) -> str:
    """What a question is embedded as: its type and topic and tags travel with
    the text, so "behavioral: conflict" questions sit near a JD about
    collaboration even when the question itself never says the word."""
    head = f"{interview_type}: {topic}" if topic else interview_type
    lines = [head, question]
    if tags:
        lines.append("tags: " + ", ".join(tags))
    return "\n".join(lines)


async def _embed_question(user_id: str, text: str) -> list[float]:
    # Raises 412 itself if the user has no Gemini key. These are documents
    # that will be searched, so they use the document embedding kind.
    return (await gateway.embed(user_id, [text], kind="doc"))[0]


async def create_question(
    user_id: str,
    interview_type: str,
    question: str,
    test_cases: list | None,
    tags: list[str] | None,
    difficulty: int | None = None,
    topic: str | None = None,
    solution_code: str | None = None,
    solution_language: str | None = None,
) -> dict:
    await _require_permission(user_id)
    if get_config(interview_type).needs_coding_platform and not (solution_code or "").strip():
        raise AppError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "solution_required",
            "Coding questions need a reference solution.",
        )
    embedding = await _embed_question(user_id, embedding_text(interview_type, question, topic, tags))
    return await questions_repo.insert_question(
        {
            "type": interview_type,
            "question": question,
            "solution_code": (solution_code or "").strip() or None,
            "solution_language": (solution_language or "").strip() or None,
            "test_cases": test_cases,
            "tags": tags or [],
            "difficulty": difficulty,
            "topic": topic,
            "embedding": embedding,
            "embed_version": EMBEDDING_VERSION,
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
    difficulty: int | None = None,
    topic: str | None = None,
    solution_code: str | None = None,
    solution_language: str | None = None,
    clear: set[str] | None = None,
) -> dict:
    await _require_permission(user_id)

    clear = clear or set()
    updates: dict = {}
    if "difficulty" in clear:
        updates["difficulty"] = None
    if solution_code is not None:
        updates["solution_code"] = solution_code.strip() or None
        if updates["solution_code"] is None:
            current = await questions_repo.get_question(question_id)
            if current and get_config(current["type"]).needs_coding_platform:
                raise AppError(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    "solution_required",
                    "Coding questions need a reference solution.",
                )
    if solution_language is not None:
        updates["solution_language"] = solution_language.strip() or None
    if test_cases is not None:
        updates["test_cases"] = test_cases
    if difficulty is not None:
        updates["difficulty"] = difficulty

    # Anything that is part of what the question is embedded as re-embeds it.
    if any(v is not None for v in (question, tags, topic)) or "topic" in clear:
        current = await questions_repo.get_question(question_id)
        if not current:
            raise AppError(status.HTTP_404_NOT_FOUND, "not_found", "Question not found")
        merged_question = question if question is not None else current["question"]
        merged_tags = tags if tags is not None else current.get("tags")
        merged_topic = None if "topic" in clear else (topic if topic is not None else current.get("topic"))
        updates.update(
            question=merged_question,
            tags=merged_tags or [],
            topic=merged_topic,
            embedding=await _embed_question(
                user_id, embedding_text(current["type"], merged_question, merged_topic, merged_tags)
            ),
            embed_version=EMBEDDING_VERSION,
        )

    if not updates:
        raise AppError(status.HTTP_422_UNPROCESSABLE_ENTITY, "validation_failed", "Nothing to update")

    row = await questions_repo.update_question(question_id, updates)
    if not row:
        raise AppError(status.HTTP_404_NOT_FOUND, "not_found", "Question not found")
    return row


async def delete_question(user_id: str, question_id: str) -> None:
    await _require_permission(user_id)
    await questions_repo.delete_question(question_id)
