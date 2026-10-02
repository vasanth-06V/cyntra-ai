-- RAG v2: labelled chunks, versioned embeddings, one-call multi-term retrieval,
-- atomic re-ingest, question selection support, and the question-bank lockdown.

-- ---------------------------------------------------------------- columns

alter table resume_chunks
  add column section text,
  add column embed_version text not null default 'legacy',
  -- keyword side of hybrid retrieval: "C#"-style tokens embed badly, exact words don't
  add column content_tsv tsvector generated always as (to_tsvector('english', content)) stored;

create index idx_resume_chunks_tsv on resume_chunks using gin (content_tsv);

alter table resumes
  add column content_hash text,   -- sha256(text + chunker version + embedding version): skip identical re-processing
  add column embed_version text;

alter table question_bank
  add column embed_version text not null default 'legacy',
  add column difficulty smallint check (difficulty between 1 and 5),
  add column topic text;

-- --------------------------------------------------- multi-term retrieval
-- One call answers every requirement of a JD. Embeddings arrive as a jsonb
-- array of arrays (PostgREST cannot be trusted to build vector[] from JSON);
-- each is cast through its text form, which is a valid vector literal.
-- Per requirement: the best `per_query` chunks by cosine similarity, whether
-- that chunk contains the term, and whether ANY chunk of the resume does.

create or replace function match_resume_chunks_multi(
  filter_resume_id uuid,
  query_embeddings jsonb,
  query_terms jsonb,
  per_query int default 1
)
returns table (
  q_idx int,
  chunk_id uuid,
  section text,
  content text,
  similarity float,
  kw_hit boolean,
  kw_any boolean
)
language sql
stable
security invoker
set search_path = public, extensions, pg_catalog
as $$
  select
    (q.i - 1)::int,
    m.id,
    m.section,
    m.content,
    m.sim,
    m.hit,
    exists (
      select 1 from resume_chunks c2
      where c2.resume_id = filter_resume_id
        and c2.content_tsv @@ plainto_tsquery('english', coalesce(query_terms ->> ((q.i - 1)::int), ''))
    )
  from jsonb_array_elements(query_embeddings) with ordinality as q(emb, i)
  cross join lateral (
    select
      c.id,
      c.section,
      c.content,
      1 - (c.embedding <=> (q.emb::text)::vector(768)) as sim,
      c.content_tsv @@ plainto_tsquery('english', coalesce(query_terms ->> ((q.i - 1)::int), '')) as hit
    from resume_chunks c
    where c.resume_id = filter_resume_id
    order by c.embedding <=> (q.emb::text)::vector(768)
    limit per_query
  ) m
$$;

-- ------------------------------------------------------ atomic re-ingest
-- Replaces a resume's chunks and marks it processed in ONE transaction, under
-- a row lock, so a failure leaves the old state intact and two concurrent
-- processings cannot interleave. Ownership is checked inside.

create or replace function replace_resume_chunks(
  p_resume_id uuid,
  p_user_id uuid,
  p_text text,
  p_content_hash text,
  p_embed_version text,
  p_chunks jsonb
)
returns int
language plpgsql
security invoker
set search_path = public, extensions, pg_catalog
as $$
declare
  n int;
begin
  perform 1 from resumes where id = p_resume_id and user_id = p_user_id for update;
  if not found then
    raise exception 'resume not found' using errcode = 'P0002';
  end if;

  delete from resume_chunks where resume_id = p_resume_id;

  insert into resume_chunks (resume_id, chunk_index, content, section, embedding, embed_version)
  select p_resume_id,
         (c ->> 'chunk_index')::int,
         c ->> 'content',
         c ->> 'section',
         (c ->> 'embedding')::vector(768),
         p_embed_version
  from jsonb_array_elements(p_chunks) c;
  get diagnostics n = row_count;

  update resumes
     set parsed_text = p_text,
         content_hash = p_content_hash,
         embed_version = p_embed_version
   where id = p_resume_id;

  return n;
end;
$$;

-- ------------------------------------------------ question-bank selection
-- Candidates for an interview: nearest questions of the type, minus ones the
-- user already met. Returns the embedding (as text) so the backend can do
-- diversity selection, and deliberately NO test cases (the answer key).

create or replace function match_question_bank_v2(
  query_embedding jsonb,
  filter_type interview_type,
  exclude_ids uuid[] default '{}',
  candidate_count int default 12
)
returns table (
  id uuid,
  question text,
  tags text[],
  difficulty smallint,
  topic text,
  similarity float,
  embedding text
)
language sql
stable
security invoker
set search_path = public, extensions, pg_catalog
as $$
  select q.id, q.question, q.tags, q.difficulty, q.topic,
         1 - (q.embedding <=> (query_embedding::text)::vector(768)),
         q.embedding::text
  from question_bank q
  where q.type = filter_type
    and q.embedding is not null
    and q.id <> all(exclude_ids)
  order by q.embedding <=> (query_embedding::text)::vector(768)
  limit candidate_count
$$;

-- ----------------------------------------------------------- permissions
-- All retrieval/ingest functions are backend-only (service role).

revoke all on function match_resume_chunks_multi(uuid, jsonb, jsonb, int) from public, anon, authenticated;
revoke all on function replace_resume_chunks(uuid, uuid, text, text, text, jsonb) from public, anon, authenticated;
revoke all on function match_question_bank_v2(jsonb, interview_type, uuid[], int) from public, anon, authenticated;
grant execute on function match_resume_chunks_multi(uuid, jsonb, jsonb, int) to service_role;
grant execute on function replace_resume_chunks(uuid, uuid, text, text, text, jsonb) to service_role;
grant execute on function match_question_bank_v2(jsonb, interview_type, uuid[], int) to service_role;

-- The old functions returned test cases to anyone able to call them.
revoke all on function match_question_bank(vector, interview_type, int) from public, anon, authenticated;
revoke all on function match_resume_chunks(vector, uuid, int) from public, anon;

-- ------------------------------------------------------------ lockdown
-- Test cases are an answer key. No signed-in user may read the table through
-- the public API; the backend (service role) serves candidates only what they
-- may see. (The web app never reads question_bank directly.)
revoke all on question_bank from anon, authenticated;
