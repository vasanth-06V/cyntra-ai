-- Move vector extension out of public schema
alter extension vector set schema extensions;

-- Move helper functions into a private schema, not exposed via PostgREST,
-- and pin search_path to fix the mutable-search-path warning.
create schema if not exists private;

drop policy if exists "roles_select_own" on roles;
drop policy if exists "roles_write_owner_only" on roles;
drop policy if exists "admin_permissions_select" on admin_permissions;
drop policy if exists "admin_permissions_write_owner_only" on admin_permissions;
drop policy if exists "question_bank_write_permission" on question_bank;
drop policy if exists "question_bank_update_permission" on question_bank;
drop policy if exists "question_bank_delete_permission" on question_bank;

drop function if exists public.is_owner(uuid);
drop function if exists public.has_admin_permission(uuid, text);

create or replace function private.is_owner(uid uuid)
returns boolean
language sql
security definer
stable
set search_path = pg_catalog, public
as $$
  select exists (select 1 from roles where user_id = uid and role = 'owner');
$$;

create or replace function private.has_admin_permission(uid uuid, perm text)
returns boolean
language sql
security definer
stable
set search_path = pg_catalog, public
as $$
  select exists (
    select 1 from roles r
    join admin_permissions ap on ap.admin_id = r.user_id
    where r.user_id = uid and r.role = 'admin' and ap.permission_key = perm
  ) or private.is_owner(uid);
$$;

-- Not exposed as a PostgREST RPC (schema "private" is not in the exposed
-- schema list); still needs EXECUTE for authenticated so RLS policies that
-- call it can actually run for signed-in users. See migration 0008 for the
-- follow-up fix after this initial revoke broke that.
revoke all on function private.is_owner(uuid) from public, anon, authenticated;
revoke all on function private.has_admin_permission(uuid, text) from public, anon, authenticated;

create policy "roles_select_own" on roles for select using (user_id = auth.uid() or private.is_owner(auth.uid()));
create policy "roles_write_owner_only" on roles for all using (private.is_owner(auth.uid())) with check (private.is_owner(auth.uid()));

create policy "admin_permissions_select" on admin_permissions for select using (admin_id = auth.uid() or private.is_owner(auth.uid()));
create policy "admin_permissions_write_owner_only" on admin_permissions for all using (private.is_owner(auth.uid())) with check (private.is_owner(auth.uid()));

create policy "question_bank_write_permission" on question_bank for insert with check (private.has_admin_permission(auth.uid(), 'manage_question_bank'));
create policy "question_bank_update_permission" on question_bank for update using (private.has_admin_permission(auth.uid(), 'manage_question_bank'));
create policy "question_bank_delete_permission" on question_bank for delete using (private.has_admin_permission(auth.uid(), 'manage_question_bank'));
