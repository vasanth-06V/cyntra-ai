-- M4.2: background jobs.
--
-- Long work (interview setup now; code runs and reports later) runs as a job
-- the page polls, instead of one request that may time out. The API process
-- runs the job; this table is its visible state. The backend is the only
-- reader and writer (service role): RLS is on with no policies, and the
-- client roles have no privileges at all.

create table jobs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references profiles(id) on delete cascade,
  kind text not null check (char_length(kind) between 1 and 40),
  status text not null default 'queued'
    check (status in ('queued', 'running', 'succeeded', 'failed')),
  subject_id uuid,          -- what the job is about (e.g. the interview being set up)
  progress text,            -- short human-readable step, shown while it runs
  result jsonb,
  error jsonb,              -- {code, message, status} when failed
  created_at timestamptz not null default now(),
  started_at timestamptz,
  heartbeat_at timestamptz,
  finished_at timestamptz
);

create index jobs_user_created_idx on jobs (user_id, created_at desc);

-- At most one active job of a kind per user: a double-click cannot start two
-- interview setups, and the second request simply finds the first.
create unique index jobs_one_active_per_kind
  on jobs (user_id, kind) where status in ('queued', 'running');

alter table jobs enable row level security;
revoke all on jobs from anon, authenticated;
