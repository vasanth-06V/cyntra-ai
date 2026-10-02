-- Fixes from the phase 1-6 database audit.

-- 1. First-user-becomes-Owner was not race-safe: two simultaneous first
--    sign-ups could both see "no owner yet". Serialize the check.
create or replace function private.handle_new_profile()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $$
begin
  perform pg_advisory_xact_lock(hashtext('cyntra_first_owner'));
  if not exists (select 1 from roles where role = 'owner') then
    insert into roles (user_id, role) values (new.id, 'owner');
  else
    insert into roles (user_id, role) values (new.id, 'user');
  end if;
  return new;
end;
$$;

-- 2. Deleting a resume used by an interview failed on the foreign key.
--    Keep the interview, forget the link (the column is already nullable).
alter table interviews drop constraint interviews_resume_id_fkey;
alter table interviews
  add constraint interviews_resume_id_fkey
  foreign key (resume_id) references resumes(id) on delete set null;

-- 3. Two concurrent turns could write the same turn_index.
create unique index interview_transcripts_interview_turn_uq
  on interview_transcripts (interview_id, turn_index);

-- 4. One row per (admin, permission) -- question_bank code uses maybe_single().
alter table admin_permissions
  add constraint admin_permissions_admin_permission_uq unique (admin_id, permission_key);

-- 5. Signed-in users could write privileged columns straight through the API
--    with their own token (e.g. provider_keys.is_valid, interviews.ends_at).
--    Only the backend (service role, unaffected by these grants) writes these
--    tables; users keep read access, and never to the encrypted key itself.
revoke insert, update, delete on provider_keys from authenticated, anon;
revoke insert, update, delete on interviews from authenticated, anon;
revoke insert, update, delete on interview_transcripts from authenticated, anon;
revoke select on provider_keys from authenticated, anon;
grant select (id, user_id, provider, slot, is_valid, last_validated_at, created_at)
  on provider_keys to authenticated;

-- 6. Defence in depth: signed-out visitors need no table access at all.
revoke all on all tables in schema public from anon;
