-- 0007 revoked EXECUTE on the private helper functions from `authenticated`
-- entirely, which breaks RLS: a policy's function call still requires the
-- querying role to hold EXECUTE, even under SECURITY DEFINER. Moving the
-- functions to schema "private" already hides them from PostgREST's RPC
-- surface (the fix for the original lint) -- the additional revoke from
-- `authenticated` was unnecessary and broke policy evaluation. Restoring it.
grant execute on function private.is_owner(uuid) to authenticated;
grant execute on function private.has_admin_permission(uuid, text) to authenticated;
