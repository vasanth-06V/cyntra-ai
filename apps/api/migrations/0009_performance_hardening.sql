-- Index every foreign key column flagged by the performance advisor.
create index if not exists idx_admin_permissions_admin_id on admin_permissions(admin_id);
create index if not exists idx_admin_permissions_granted_by on admin_permissions(granted_by);
create index if not exists idx_interview_reports_interview_id on interview_reports(interview_id);
create index if not exists idx_interview_transcripts_interview_id on interview_transcripts(interview_id);
create index if not exists idx_interviews_resume_id on interviews(resume_id);
create index if not exists idx_interviews_user_id on interviews(user_id);
create index if not exists idx_question_bank_created_by on question_bank(created_by);
create index if not exists idx_resumes_user_id on resumes(user_id);

-- Rewrite every policy to call (select auth.uid()) / wrap the innermost
-- auth.uid() so Postgres evaluates it once per query (via initPlan) instead
-- of once per row. Also splits the "for all" owner policies on roles and
-- admin_permissions into insert/update/delete only, since select was already
-- covered by "_select_*" -- having both meant two permissive policies were
-- evaluated for every SELECT (the "multiple_permissive_policies" warning).

drop policy if exists "profiles_select_own" on profiles;
drop policy if exists "profiles_update_own" on profiles;
drop policy if exists "profiles_insert_own" on profiles;
create policy "profiles_select_own" on profiles for select using (id = (select auth.uid()));
create policy "profiles_update_own" on profiles for update using (id = (select auth.uid()));
create policy "profiles_insert_own" on profiles for insert with check (id = (select auth.uid()));

drop policy if exists "roles_select_own" on roles;
drop policy if exists "roles_write_owner_only" on roles;
create policy "roles_select_own" on roles for select using (
  user_id = (select auth.uid()) or (select private.is_owner(auth.uid()))
);
create policy "roles_insert_owner_only" on roles for insert with check (private.is_owner((select auth.uid())));
create policy "roles_update_owner_only" on roles for update using (private.is_owner((select auth.uid())));
create policy "roles_delete_owner_only" on roles for delete using (private.is_owner((select auth.uid())));

drop policy if exists "admin_permissions_select" on admin_permissions;
drop policy if exists "admin_permissions_write_owner_only" on admin_permissions;
create policy "admin_permissions_select" on admin_permissions for select using (
  admin_id = (select auth.uid()) or (select private.is_owner(auth.uid()))
);
create policy "admin_permissions_insert_owner_only" on admin_permissions for insert with check (private.is_owner((select auth.uid())));
create policy "admin_permissions_update_owner_only" on admin_permissions for update using (private.is_owner((select auth.uid())));
create policy "admin_permissions_delete_owner_only" on admin_permissions for delete using (private.is_owner((select auth.uid())));

drop policy if exists "provider_keys_owner_only" on provider_keys;
create policy "provider_keys_owner_only" on provider_keys for all
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));

drop policy if exists "resumes_owner_only" on resumes;
create policy "resumes_owner_only" on resumes for all
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));

drop policy if exists "interviews_owner_only" on interviews;
create policy "interviews_owner_only" on interviews for all
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));

drop policy if exists "interview_transcripts_owner_only" on interview_transcripts;
create policy "interview_transcripts_owner_only" on interview_transcripts for all using (
  exists (select 1 from interviews i where i.id = interview_id and i.user_id = (select auth.uid()))
) with check (
  exists (select 1 from interviews i where i.id = interview_id and i.user_id = (select auth.uid()))
);

drop policy if exists "question_bank_select_all" on question_bank;
drop policy if exists "question_bank_write_permission" on question_bank;
drop policy if exists "question_bank_update_permission" on question_bank;
drop policy if exists "question_bank_delete_permission" on question_bank;
create policy "question_bank_select_all" on question_bank for select using ((select auth.uid()) is not null);
create policy "question_bank_write_permission" on question_bank for insert with check (private.has_admin_permission((select auth.uid()), 'manage_question_bank'));
create policy "question_bank_update_permission" on question_bank for update using (private.has_admin_permission((select auth.uid()), 'manage_question_bank'));
create policy "question_bank_delete_permission" on question_bank for delete using (private.has_admin_permission((select auth.uid()), 'manage_question_bank'));

drop policy if exists "interview_reports_owner_only" on interview_reports;
create policy "interview_reports_owner_only" on interview_reports for all using (
  exists (select 1 from interviews i where i.id = interview_id and i.user_id = (select auth.uid()))
) with check (
  exists (select 1 from interviews i where i.id = interview_id and i.user_id = (select auth.uid()))
);
