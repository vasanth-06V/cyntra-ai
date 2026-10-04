-- Final-audit hardening (2026-10-04).
--
-- 1. Client write privileges. Signed-in users held table-level INSERT/UPDATE/
--    DELETE on tables the web app never writes (chat_messages, resume_chunks,
--    llm_usage, roles, admin_permissions ...). Row-level security limited them
--    to their own rows, but nothing limited HOW MANY: any Google account could
--    fill the free 500 MB database with its own JWT and the public anon key.
--    The backend (service role) is unaffected by these grants. What the web app
--    really does with the user's own session:
--      profiles       insert (id, full_name)   -- account setup
--      conversations  delete                    -- delete a chat
--      notifications  update (is_read)          -- mark read
--    everything else is read-only for clients. (roles/admin_permissions are now
--    written by the Team endpoints only, which also protects the Owner role.)
-- 2. admin_permissions carried the same unique constraint twice (0019 and 0021).
-- 3. Three indexes are prefixes of unique indexes that already exist.
-- 4. Deleting a user who granted permissions or created questions failed on a
--    foreign key with no ON DELETE action: clear the reference instead.
-- 5. Foreign keys without an index (code_submissions.user_id / question_id).
-- 6. A dead policy that would expose reference solutions if SELECT were ever
--    re-granted on question_bank.

-- 1 ------------------------------------------------------------------------
revoke insert, update, delete on chat_messages, resume_chunks, llm_usage, roles, admin_permissions
  from authenticated;

revoke insert, update, delete on conversations from authenticated;
grant delete on conversations to authenticated;

revoke insert, update, delete on notifications from authenticated;
grant update (is_read) on notifications to authenticated;

revoke insert, update, delete on profiles from authenticated;
grant insert (id, full_name) on profiles to authenticated;

-- 2 ------------------------------------------------------------------------
alter table admin_permissions drop constraint if exists admin_permissions_admin_key_unique;

-- 3 ------------------------------------------------------------------------
drop index if exists idx_admin_permissions_admin_id;
drop index if exists idx_interview_transcripts_interview_id;
drop index if exists idx_interview_reports_interview_id;

-- 4 ------------------------------------------------------------------------
alter table admin_permissions drop constraint if exists admin_permissions_granted_by_fkey;
alter table admin_permissions
  add constraint admin_permissions_granted_by_fkey
  foreign key (granted_by) references profiles(id) on delete set null;

alter table question_bank drop constraint if exists question_bank_created_by_fkey;
alter table question_bank
  add constraint question_bank_created_by_fkey
  foreign key (created_by) references profiles(id) on delete set null;

-- 5 ------------------------------------------------------------------------
create index if not exists code_submissions_user_idx on code_submissions (user_id);
create index if not exists code_submissions_question_idx on code_submissions (question_id);

-- 6 ------------------------------------------------------------------------
drop policy if exists question_bank_select_all on question_bank;
