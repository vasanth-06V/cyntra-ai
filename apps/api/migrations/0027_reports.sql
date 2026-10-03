-- Phase 9: interview reports.
--
-- interview_reports existed since 0005 but was never used. It becomes a
-- backend-only table (like jobs): the API is the only reader and writer, so
-- the 7-day expiry is enforced in exactly one place (at read time, plus a
-- purge sweep) and cannot be bypassed by a direct client query.
--
-- Safe to run only while the table is empty (it has never been written to):
-- the NOT NULL steps fail, and the whole migration rolls back, otherwise.

alter table interview_reports
  add column user_id uuid references profiles(id) on delete cascade,
  add column overall_score smallint check (overall_score between 0 and 100),
  add column interview_type text;

alter table interview_reports
  alter column user_id set not null,
  alter column overall_score set not null,
  alter column interview_type set not null,
  alter column interview_id set not null,
  alter column report_data set not null,
  alter column expires_at set default (now() + interval '7 days');

-- One report per interview (regenerating replaces it).
alter table interview_reports
  add constraint interview_reports_one_per_interview unique (interview_id);

create index interview_reports_user_idx on interview_reports (user_id, created_at desc);
create index interview_reports_expires_idx on interview_reports (expires_at);

drop policy if exists "interview_reports_owner_only" on interview_reports;
alter table interview_reports enable row level security;
revoke all on interview_reports from anon, authenticated;
