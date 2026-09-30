create table resumes (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references profiles(id) on delete cascade,
  file_url text not null,
  parsed_text text,
  embedding vector(768),
  created_at timestamptz default now()
);
