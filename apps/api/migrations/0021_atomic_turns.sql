-- M4.1: atomic interview turns and a unique admin permission grant.
--
-- 1. append_interview_turns: the candidate's answer and the interviewer's reply
--    are written together, with the next turn_index computed under a row lock on
--    the interview. Before this, the index was read and then inserted in two
--    separate calls, so a double-click could collide, and a failure between the
--    two inserts could leave an answer without a reply.
-- 2. admin_permissions gets UNIQUE (admin_id, permission_key): a duplicated
--    grant used to make permission lookups fail.

-- 1 ---------------------------------------------------------------------------
create or replace function append_interview_turns(
  p_interview_id uuid,
  p_user_id uuid,
  p_user_text text,
  p_ai_text text
) returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  v_next integer;
begin
  -- Ownership is checked here too: this function is the only writer, and it
  -- must not trust its caller to have checked.
  perform 1 from interviews where id = p_interview_id and user_id = p_user_id for update;
  if not found then
    raise exception 'interview not found' using errcode = 'P0002';
  end if;

  select coalesce(max(turn_index) + 1, 0) into v_next
    from interview_transcripts where interview_id = p_interview_id;

  insert into interview_transcripts (interview_id, turn_index, speaker, text)
  values (p_interview_id, v_next, 'user', p_user_text),
         (p_interview_id, v_next + 1, 'ai', p_ai_text);

  return v_next;
end;
$$;

revoke all on function append_interview_turns(uuid, uuid, text, text) from public, anon, authenticated;
grant execute on function append_interview_turns(uuid, uuid, text, text) to service_role;

-- 2 ---------------------------------------------------------------------------
-- Remove accidental duplicates first (keep the oldest grant of each pair).
delete from admin_permissions a
using admin_permissions b
where a.admin_id = b.admin_id
  and a.permission_key = b.permission_key
  and (a.created_at, a.id) > (b.created_at, b.id);

alter table admin_permissions
  add constraint admin_permissions_admin_key_unique unique (admin_id, permission_key);
