-- The Interviewing Agent is restricted to Gemini/Groq (Section 8 of the
-- plan); the DB enum still technically allows 'claude' but app-level
-- validation (a restricted Pydantic Literal) is what actually enforces the
-- restriction, same as other app-level-only constraints in this schema.
alter table interviews add column provider provider_name not null default 'gemini';
