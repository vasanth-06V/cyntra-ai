-- Supports the text-mode orchestration core: a running summary keeps token
-- usage flat as the interview gets long (Section 8.3 of the plan), and the
-- selected question tracking lets coding-type interviews know which of
-- their RAG-selected questions is currently active.
alter table interviews add column running_summary text;
alter table interviews add column selected_question_ids uuid[] default '{}';
alter table interviews add column current_question_index int default 0;
