-- Daily per-user LLM consumption, so quota use is visible in the app instead
-- of only in Google's console. 'embed' is tracked separately from 'chat'
-- because providers meter them against different quotas.
create table llm_usage (
  user_id uuid not null references profiles(id) on delete cascade,
  provider provider_name not null,
  kind text not null check (kind in ('chat', 'embed')),
  day date not null default ((now() at time zone 'utc')::date),
  requests int not null default 0,
  input_tokens bigint not null default 0,
  output_tokens bigint not null default 0,
  primary key (user_id, provider, kind, day)
);

alter table llm_usage enable row level security;

-- Users can read their own usage; only the backend (service role, which
-- bypasses RLS) writes it.
create policy "llm_usage_select_own" on llm_usage
  for select using (user_id = (select auth.uid()));

create or replace function record_llm_usage(
  p_user_id uuid,
  p_provider provider_name,
  p_kind text,
  p_requests int,
  p_input bigint,
  p_output bigint
)
returns void
language sql
set search_path = public, pg_catalog
as $$
  insert into llm_usage (user_id, provider, kind, day, requests, input_tokens, output_tokens)
  values (p_user_id, p_provider, p_kind, (now() at time zone 'utc')::date, p_requests, p_input, p_output)
  on conflict (user_id, provider, kind, day) do update set
    requests = llm_usage.requests + excluded.requests,
    input_tokens = llm_usage.input_tokens + excluded.input_tokens,
    output_tokens = llm_usage.output_tokens + excluded.output_tokens;
$$;

-- Not callable by signed-in users through the API; the backend uses the
-- service role.
revoke all on function record_llm_usage(uuid, provider_name, text, int, bigint, bigint)
  from public, anon, authenticated;
