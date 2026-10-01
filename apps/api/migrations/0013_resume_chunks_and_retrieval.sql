-- Real RAG retrieval needs per-chunk embeddings so a JD requirement can
-- match the specific relevant resume section, not just the whole document
-- at once. The original resumes.embedding (one vector per resume) can't
-- support that -- superseded by this table.
create table resume_chunks (
  id uuid primary key default gen_random_uuid(),
  resume_id uuid references resumes(id) on delete cascade,
  chunk_index int not null,
  content text not null,
  embedding vector(768),
  created_at timestamptz default now()
);

create index idx_resume_chunks_resume_id on resume_chunks(resume_id);

alter table resume_chunks enable row level security;

create policy "resume_chunks_owner_only" on resume_chunks for all using (
  exists (select 1 from resumes r where r.id = resume_id and r.user_id = (select auth.uid()))
) with check (
  exists (select 1 from resumes r where r.id = resume_id and r.user_id = (select auth.uid()))
);

alter table resumes drop column embedding;

-- pgvector cosine-similarity RPCs (plain, non-SECURITY DEFINER -- these run
-- with the caller's own privileges, so RLS on the underlying tables still
-- applies normally if called by a regular authenticated user via PostgREST).
create or replace function match_resume_chunks(
  query_embedding vector(768),
  filter_resume_id uuid,
  match_count int default 5
)
returns table (id uuid, content text, chunk_index int, similarity float)
language sql
stable
set search_path = public, extensions, pg_catalog
as $$
  select id, content, chunk_index, 1 - (embedding <=> query_embedding) as similarity
  from resume_chunks
  where resume_id = filter_resume_id
  order by embedding <=> query_embedding
  limit match_count;
$$;

create or replace function match_question_bank(
  query_embedding vector(768),
  filter_type interview_type,
  match_count int default 5
)
returns table (id uuid, question text, test_cases jsonb, tags text[], similarity float)
language sql
stable
set search_path = public, extensions, pg_catalog
as $$
  select id, question, test_cases, tags, 1 - (embedding <=> query_embedding) as similarity
  from question_bank
  where type = filter_type
  order by embedding <=> query_embedding
  limit match_count;
$$;
