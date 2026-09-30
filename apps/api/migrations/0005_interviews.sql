create type interview_type as enum (
  'coding', 'behavioral', 'hr', 'ml_ai', 'webd', 'sde', 'system_design', 'case_study'
);
create type interview_status as enum ('setting_up', 'in_progress', 'completed', 'aborted');

create table interviews (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references profiles(id) on delete cascade,
  type interview_type not null,
  jd_text text not null,
  resume_id uuid references resumes(id),
  status interview_status not null default 'setting_up',
  phase text,
  started_at timestamptz,
  ends_at timestamptz,
  created_at timestamptz default now()
);

create table interview_transcripts (
  id uuid primary key default gen_random_uuid(),
  interview_id uuid references interviews(id) on delete cascade,
  turn_index int not null,
  speaker text not null,
  text text not null,
  created_at timestamptz default now()
);

create table question_bank (
  id uuid primary key default gen_random_uuid(),
  type interview_type not null,
  question text not null,
  test_cases jsonb,
  tags text[],
  embedding vector(768),
  created_by uuid references profiles(id),
  created_at timestamptz default now()
);

create table interview_reports (
  id uuid primary key default gen_random_uuid(),
  interview_id uuid references interviews(id) on delete cascade,
  report_data jsonb not null,
  created_at timestamptz default now(),
  expires_at timestamptz not null
);
