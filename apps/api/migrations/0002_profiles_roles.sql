create table profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text,
  created_at timestamptz default now()
);

create type role_type as enum ('owner', 'admin', 'user');

create table roles (
  user_id uuid primary key references profiles(id) on delete cascade,
  role role_type not null default 'user'
);

create table admin_permissions (
  id uuid primary key default gen_random_uuid(),
  admin_id uuid references profiles(id) on delete cascade,
  permission_key text not null,
  granted_by uuid references profiles(id),
  created_at timestamptz default now()
);
