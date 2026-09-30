create type provider_name as enum ('gemini', 'claude', 'groq');
create type key_slot as enum ('primary', 'backup');

create table provider_keys (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references profiles(id) on delete cascade,
  provider provider_name not null,
  slot key_slot not null,
  encrypted_key text not null,
  is_valid boolean default false,
  last_validated_at timestamptz,
  created_at timestamptz default now(),
  unique (user_id, provider, slot)
);
