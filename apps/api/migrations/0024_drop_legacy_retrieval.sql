-- The original single-vector retrieval functions are replaced by
-- match_resume_chunks_multi / match_question_bank_v2 (migration 0020). They also
-- returned test cases to any caller; nothing uses them any more.
drop function if exists match_resume_chunks(vector, uuid, int);
drop function if exists match_question_bank(vector, interview_type, int);
