"""Retrieval entry points. The SQL lives in app/db; these names stay here so
the rest of the code imports retrieval from one place."""

from app.db.questions import match_question_bank, match_question_bank_v2
from app.db.resumes import match_resume_chunks, match_resume_chunks_multi

__all__ = [
    "match_question_bank",
    "match_question_bank_v2",
    "match_resume_chunks",
    "match_resume_chunks_multi",
]
