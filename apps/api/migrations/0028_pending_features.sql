-- Pending features: resume rename + database-enforced limits, ATS history.
--
-- 1. resumes.display_name: an optional friendly name (the owner may rename).
-- 2. A signed-in user could write ANY column of their own resumes row straight
--    through the public API (including parsed_text and file_key). Client writes
--    are now limited to the columns the app really sets: insert (id, user_id,
--    file_key), update (display_name). The backend (service role) is unaffected.
-- 3. file_key must live under the owner's own folder (resumes/<uid>/...), so a
--    forged key can never point at another user's file.
-- 4. At most 3 resumes per user, enforced by a trigger (race-safe), not only by
--    the web handler.
-- 5. ats_scores: the last 10 ATS results per resume, backend-only; a function
--    stores a result and prunes older ones atomically.

-- 1 ------------------------------------------------------------------------
alter table resumes
  add column display_name text
  check (display_name is null or char_length(display_name) between 1 and 80);

-- 2 ------------------------------------------------------------------------
revoke insert, update on resumes from anon, authenticated;
grant insert (id, user_id, file_key) on resumes to authenticated;
grant update (display_name) on resumes to authenticated;

-- 3 ------------------------------------------------------------------------
alter table resumes
  add constraint resumes_file_key_own_folder
  check (file_key like 'resumes/' || user_id::text || '/%' and file_key not like '%..%');

-- 4 ------------------------------------------------------------------------
create or replace function enforce_resume_limit()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  -- Serialise concurrent uploads of one user so two cannot both pass the count.
  perform pg_advisory_xact_lock(hashtext('resume_limit:' || new.user_id::text));
  if (select count(*) from resumes where user_id = new.user_id) >= 3 then
    raise exception 'resume_limit: you can keep up to 3 resumes' using errcode = 'P0001';
  end if;
  return new;
end;
$$;

create trigger resumes_limit_before_insert
  before insert on resumes
  for each row execute function enforce_resume_limit();

-- 5 ------------------------------------------------------------------------
create table ats_scores (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references profiles(id) on delete cascade,
  resume_id uuid not null references resumes(id) on delete cascade,
  job_title text,
  jd_excerpt text,
  provider text not null,
  composite_score smallint not null check (composite_score between 0 and 100),
  result jsonb not null,
  created_at timestamptz not null default now()
);

create index ats_scores_resume_idx on ats_scores (resume_id, created_at desc);
create index ats_scores_user_idx on ats_scores (user_id, created_at desc);

alter table ats_scores enable row level security;
revoke all on ats_scores from anon, authenticated;

create or replace function record_ats_score(
  p_user_id uuid,
  p_resume_id uuid,
  p_job_title text,
  p_jd_excerpt text,
  p_provider text,
  p_composite integer,
  p_result jsonb,
  p_keep integer default 10
) returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_id uuid;
begin
  -- Ownership is checked here, and the row lock serialises two checks of one resume.
  perform 1 from resumes where id = p_resume_id and user_id = p_user_id for update;
  if not found then
    raise exception 'resume not found' using errcode = 'P0002';
  end if;

  insert into ats_scores (user_id, resume_id, job_title, jd_excerpt, provider, composite_score, result)
  values (p_user_id, p_resume_id, p_job_title, p_jd_excerpt, p_provider, p_composite, p_result)
  returning id into v_id;

  delete from ats_scores
  where resume_id = p_resume_id
    and id not in (
      select id from ats_scores where resume_id = p_resume_id
      order by created_at desc, id desc limit p_keep
    );

  return v_id;
end;
$$;

revoke all on function record_ats_score(uuid, uuid, text, text, text, integer, jsonb, integer)
  from public, anon, authenticated;
grant execute on function record_ats_score(uuid, uuid, text, text, text, integer, jsonb, integer)
  to service_role;
