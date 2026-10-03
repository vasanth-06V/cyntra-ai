-- Phase 7: the coding round.
--
-- The question bank keeps a reference solution per coding question. It is
-- never sent to candidates: question_bank has had all client privileges
-- revoked since 0020, and the retrieval function returns no solution column.
-- A candidate's single submission per problem is stored with its language, the
-- reviewer's verdict (hidden from the candidate) and a short summary the
-- interviewer sees on later turns.

alter table question_bank
  add column if not exists solution_code text,
  add column if not exists solution_language text;

create table code_submissions (
  id uuid primary key default gen_random_uuid(),
  interview_id uuid not null references interviews(id) on delete cascade,
  user_id uuid not null references profiles(id) on delete cascade,
  question_id uuid references question_bank(id) on delete set null,
  language text not null check (char_length(language) between 1 and 30),
  code text not null check (char_length(code) between 1 and 8000),
  line_count integer not null check (line_count >= 1),
  status text not null default 'review' check (status in ('review', 'done', 'failed')),
  verdict jsonb,
  summary text,
  created_at timestamptz not null default now()
);

-- One submission per problem. A failed review (provider outage) does not use
-- the candidate's submit: failed rows are excluded from the rule.
create unique index code_submissions_one_per_problem
  on code_submissions (interview_id, question_id) where status <> 'failed';

create index code_submissions_interview_idx on code_submissions (interview_id, created_at);

alter table code_submissions enable row level security;
revoke all on code_submissions from anon, authenticated;
