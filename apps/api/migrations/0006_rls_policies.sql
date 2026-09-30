-- Helper functions (security definer to avoid recursive RLS lookups)
create or replace function is_owner(uid uuid)
returns boolean
language sql
security definer
stable
as $$
  select exists (select 1 from roles where user_id = uid and role = 'owner');
$$;

create or replace function has_admin_permission(uid uuid, perm text)
returns boolean
language sql
security definer
stable
as $$
  select exists (
    select 1 from roles r
    join admin_permissions ap on ap.admin_id = r.user_id
    where r.user_id = uid and r.role = 'admin' and ap.permission_key = perm
  ) or is_owner(uid);
$$;

-- profiles
alter table profiles enable row level security;
create policy "profiles_select_own" on profiles for select using (id = auth.uid());
create policy "profiles_update_own" on profiles for update using (id = auth.uid());
create policy "profiles_insert_own" on profiles for insert with check (id = auth.uid());

-- roles: readable by self, writable only by Owner
alter table roles enable row level security;
create policy "roles_select_own" on roles for select using (user_id = auth.uid() or is_owner(auth.uid()));
create policy "roles_write_owner_only" on roles for all using (is_owner(auth.uid())) with check (is_owner(auth.uid()));

-- admin_permissions: writable only by Owner
alter table admin_permissions enable row level security;
create policy "admin_permissions_select" on admin_permissions for select using (admin_id = auth.uid() or is_owner(auth.uid()));
create policy "admin_permissions_write_owner_only" on admin_permissions for all using (is_owner(auth.uid())) with check (is_owner(auth.uid()));

-- provider_keys: owner-of-row only
alter table provider_keys enable row level security;
create policy "provider_keys_owner_only" on provider_keys for all using (user_id = auth.uid()) with check (user_id = auth.uid());

-- resumes: owner-of-row only
alter table resumes enable row level security;
create policy "resumes_owner_only" on resumes for all using (user_id = auth.uid()) with check (user_id = auth.uid());

-- interviews: owner-of-row only
alter table interviews enable row level security;
create policy "interviews_owner_only" on interviews for all using (user_id = auth.uid()) with check (user_id = auth.uid());

-- interview_transcripts: accessible if the parent interview belongs to the user
alter table interview_transcripts enable row level security;
create policy "interview_transcripts_owner_only" on interview_transcripts for all using (
  exists (select 1 from interviews i where i.id = interview_id and i.user_id = auth.uid())
) with check (
  exists (select 1 from interviews i where i.id = interview_id and i.user_id = auth.uid())
);

-- question_bank: readable by all authenticated users, writable by Owner/Admin with permission
alter table question_bank enable row level security;
create policy "question_bank_select_all" on question_bank for select using (auth.uid() is not null);
create policy "question_bank_write_permission" on question_bank for insert with check (has_admin_permission(auth.uid(), 'manage_question_bank'));
create policy "question_bank_update_permission" on question_bank for update using (has_admin_permission(auth.uid(), 'manage_question_bank'));
create policy "question_bank_delete_permission" on question_bank for delete using (has_admin_permission(auth.uid(), 'manage_question_bank'));

-- interview_reports: accessible if the parent interview belongs to the user
alter table interview_reports enable row level security;
create policy "interview_reports_owner_only" on interview_reports for all using (
  exists (select 1 from interviews i where i.id = interview_id and i.user_id = auth.uid())
) with check (
  exists (select 1 from interviews i where i.id = interview_id and i.user_id = auth.uid())
);
