create table conversations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references profiles(id) on delete cascade,
  title text,
  created_at timestamptz default now()
);

create table chat_messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid references conversations(id) on delete cascade,
  role text not null,          -- 'user' | 'assistant'
  provider text,                -- which provider generated this (null for user messages)
  content text not null,
  created_at timestamptz default now()
);

create index idx_conversations_user_id on conversations(user_id);
create index idx_chat_messages_conversation_id on chat_messages(conversation_id);

alter table conversations enable row level security;
alter table chat_messages enable row level security;

create policy "conversations_owner_only" on conversations for all
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));

create policy "chat_messages_owner_only" on chat_messages for all using (
  exists (select 1 from conversations c where c.id = conversation_id and c.user_id = (select auth.uid()))
) with check (
  exists (select 1 from conversations c where c.id = conversation_id and c.user_id = (select auth.uid()))
);
