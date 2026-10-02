-- Usage accounting that matches how providers actually count.
--
-- 1. Gemini's daily quota resets at midnight *Pacific*, not UTC, so the day a
--    call is booked to is now chosen by the backend (p_day); with no p_day the
--    old UTC behaviour applies.
-- 2. Reasoning ("thinking") tokens are billed like output but reported
--    separately; they get their own counter.
--
-- The new parameters have defaults, so a caller that still sends the old six
-- arguments keeps working.

alter table llm_usage add column thought_tokens bigint not null default 0;

drop function if exists record_llm_usage(uuid, provider_name, text, int, bigint, bigint);

create function record_llm_usage(
  p_user_id uuid,
  p_provider provider_name,
  p_kind text,
  p_requests int,
  p_input bigint,
  p_output bigint,
  p_thought bigint default 0,
  p_day date default null
)
returns void
language sql
set search_path = public, pg_catalog
as $$
  insert into llm_usage (user_id, provider, kind, day, requests, input_tokens, output_tokens, thought_tokens)
  values (
    p_user_id, p_provider, p_kind,
    coalesce(p_day, (now() at time zone 'utc')::date),
    p_requests, p_input, p_output, p_thought
  )
  on conflict (user_id, provider, kind, day) do update set
    requests = llm_usage.requests + excluded.requests,
    input_tokens = llm_usage.input_tokens + excluded.input_tokens,
    output_tokens = llm_usage.output_tokens + excluded.output_tokens,
    thought_tokens = llm_usage.thought_tokens + excluded.thought_tokens;
$$;

-- Not callable by signed-in users through the API; the backend uses the
-- service role.
revoke all on function record_llm_usage(uuid, provider_name, text, int, bigint, bigint, bigint, date)
  from public, anon, authenticated;
grant execute on function record_llm_usage(uuid, provider_name, text, int, bigint, bigint, bigint, date)
  to service_role;
