-- The first user ever to complete account-setup (i.e. get a `profiles` row)
-- automatically becomes Owner; everyone after that defaults to 'user'.
-- Implemented as a trigger (not client-side logic) because the client's
-- RLS policies on `roles` require an existing Owner to write to that table
-- at all -- a brand new user could never insert their own role row
-- otherwise. Runs SECURITY DEFINER so it isn't subject to that same RLS
-- restriction.
create or replace function private.handle_new_profile()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
begin
  if not exists (select 1 from roles where role = 'owner') then
    insert into roles (user_id, role) values (new.id, 'owner');
  else
    insert into roles (user_id, role) values (new.id, 'user');
  end if;
  return new;
end;
$$;

create trigger on_profile_created
after insert on profiles
for each row execute function private.handle_new_profile();
