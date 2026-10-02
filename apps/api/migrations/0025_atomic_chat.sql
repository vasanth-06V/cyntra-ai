-- M4.3: a chat exchange (the user's message and the assistant's reply) is
-- stored in ONE transaction. Before, two separate inserts could leave a user
-- message without its reply. The two rows get distinct, ordered timestamps
-- (clock_timestamp, not now(): inside one transaction now() is constant, and
-- the history is ordered by created_at).

create or replace function append_chat_exchange(
  p_conversation_id uuid,
  p_user_id uuid,
  p_user_text text,
  p_assistant_text text,
  p_provider text
) returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  -- Ownership is checked here: this function is the only writer and must not
  -- trust its caller to have checked.
  perform 1 from conversations where id = p_conversation_id and user_id = p_user_id for update;
  if not found then
    raise exception 'conversation not found' using errcode = 'P0002';
  end if;

  insert into chat_messages (conversation_id, role, content, provider, created_at)
  values
    (p_conversation_id, 'user', p_user_text, null, clock_timestamp()),
    (p_conversation_id, 'assistant', p_assistant_text, p_provider,
     clock_timestamp() + interval '1 millisecond');
end;
$$;

revoke all on function append_chat_exchange(uuid, uuid, text, text, text) from public, anon, authenticated;
grant execute on function append_chat_exchange(uuid, uuid, text, text, text) to service_role;
