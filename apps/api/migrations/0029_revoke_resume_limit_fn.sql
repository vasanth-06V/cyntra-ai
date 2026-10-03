-- The limit function is a trigger body only; it must not be callable through the REST API.
revoke all on function enforce_resume_limit() from public, anon, authenticated;
