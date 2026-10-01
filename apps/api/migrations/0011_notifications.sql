-- Backs the "notify user after key failover" requirement from the BYOK
-- design (Section 6.3): a one-shot notification row created by the backend
-- (service role, bypasses RLS) after a primary key fails over to backup.
create table notifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references profiles(id) on delete cascade,
  message text not null,
  is_read boolean default false,
  created_at timestamptz default now()
);

create index idx_notifications_user_id on notifications(user_id);

alter table notifications enable row level security;

create policy "notifications_select_own" on notifications for select using (user_id = (select auth.uid()));
create policy "notifications_update_own" on notifications for update using (user_id = (select auth.uid()));
-- No insert/delete policy for anon/authenticated -- only the backend
-- (service role, which bypasses RLS) creates notifications.
