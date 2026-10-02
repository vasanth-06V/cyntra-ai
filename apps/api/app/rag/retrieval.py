"""Retrieval entry points. The SQL lives in app/db; these names stay here so
the rest of the code imports retrieval from one place."""

from app.db.questions import match_question_bank
from app.db.resumes import match_resume_chunks

__all__ = ["match_question_bank", "match_resume_chunks"]
