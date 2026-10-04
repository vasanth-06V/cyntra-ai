# CyntraAI final audit: database, docs and cross-cutting partition

Audit date 2026-10-04. Repo HEAD `369b8cb` (74 commits, working tree clean at start). Live database: Supabase project `erdsnljuppltvmvivugv` (Postgres 17.11, pgvector 0.8.2), inspected read-only (information_schema, pg_catalog, pg_policies, `list_migrations`, `get_advisors`, counts only). No DDL/DML was run, no LLM provider was called, `.env` files were not read.

## 1. Summary

**Inspected:** 29 migration files (1,091 lines, read in full), the live catalog (17 tables, 25 policies, 7 functions, 2 triggers, 43 indexes, 56 constraints, 1 storage bucket, 30 applied migrations), all 14 `app/db/*.py` repository modules, every direct Supabase call in `apps/web` (11 files), 11 docs (about 2,400 lines, read in full), `.github/workflows/ci.yml`, both `.gitignore` files, `.claude/launch.json`, `git ls-files` (406 files), `git log` (74 commits) and a secret-pattern scan of the whole history. I also replayed CI from a fresh clone (backend and web), and ran `npm audit`, `npm outdated`, `pip list --outdated` and `pip-audit`.

**Verdicts**

| # | Check | Verdict |
|---|---|---|
| 1 | Migrations vs live schema | **No functional drift.** Cosmetic history drift (one applied migration with no file, names and application order differ) and one self-made duplicate unique constraint |
| 2 | Code vs schema contract | **Match.** No missing table, column, RPC or parameter; unique-index error handling matches (23505); P0002 unmapped (low) |
| 3 | Database security | **Strong isolation, loose write grants.** Backend-only tables and `question_bank` are unreachable; no SECURITY DEFINER exposure; `provider_keys.encrypted_key` unreachable. Weak spot: unbounded direct client writes (H-01) |
| 4 | Docs vs reality | **PRODUCT.md and the documentary snapshot are materially stale** (R2, Judge0, stubs, "no ATS history", test counts); corrections in section 6 |
| 5 | Completeness | Every planned feature is built, redesigned or explicitly dropped. **4 of 22 feature rows are verified live; 18 have never touched live data** (0 interviews, 0 reports, 0 ATS rows, empty question bank). Deployment files and two CI gates are missing |
| 6 | CI and hygiene | **CI web job fails on a clean checkout** (H-02) and the repo has **no git remote**. No tracked secrets or generated files; CRLF/LF policy missing |
| 7 | Secrets and config | **No secret in the tree or its history.** No `NEXT_PUBLIC_` secret. Web has no `.env.example` |
| 8 | Dependencies | 0 critical npm advisories (2 low in production); Python pins carry real advisories (starlette, cryptography, pdfminer.six, python-jose) |
| 9 | Operations | Single-worker design is consistent; health/ready/validation good; retention only for reports; deployment files not written; free-tier pause undocumented |

**Top findings:** H-01 unbounded direct client writes can exhaust the free database; H-02 CI red on clean checkout; M-01 two FKs block user deletion; M-02 no git remote; M-03 migrations never replayed on a fresh database; M-04 boot recovery fails all jobs; M-05 unpinned Gemini alias; M-07 empty question bank; M-08 demo/email sign-up path; M-09 stale docs; M-10 vulnerable Python pins. Totals: 0 critical, 2 high, 10 medium, 17 low, 8 items needing verification (section 12).

**Test and build facts (verified today):** backend 605 passed + 1 skipped; frontend 158 passed (24 files); clean-clone replay: pytest, eslint, vitest and `next build` pass, standalone `tsc` fails (H-02).

Sections follow the brief: 2 schema drift, 3 contract, 4 security matrix, 5 advisors, 6 docs corrections, 7 feature/plan checklist, 8 CI/repo, 9 secrets/env, 10 dependencies, 11 operations, 12 findings, 13 upgrades.

---

## 2. Schema drift: migrations 0001-0029 vs the live database

Method: every migration was read in order and a running model of the schema built, then diffed with the live catalog. Result: **no functional drift**. Differences found are naming/metadata only, plus two redundant objects that the migrations themselves created.

### 2.1 Migration history

| Check | Result |
|---|---|
| Files numbered 0001..0029, no gaps, no duplicate numbers | OK (29 files, contiguous) |
| Live `list_migrations` count | 30 entries vs 29 files |
| Extra applied migration with no file | `fix_remaining_rls_initplan` (applied 2026-09-30, between `performance_hardening` and `auto_assign_role...`). Its effect (wrapping `auth.uid()` in `(select ...)` on the remaining policies) is already folded into the repo's `0009_performance_hardening.sql`, whose live policy text matches. So the file for it was merged into 0009 after the fact. Drift in history, not in schema. |
| Applied names differ from file names | Yes. Early ones are unprefixed (`enable_pgvector`, `interviews_schema` = 0005, `chat_conversations` = 0012, `interview_brief_and_resume_digest` = 0018, `llm_usage_v2` = 0023, `rag_v2` = 0020, `drop_legacy_retrieval` = 0024); from 0021 on the applied name carries the number (`0021_atomic_turns`, `0022_jobs`, `0025_atomic_chat`, ...). Cosmetic, but a future `supabase db push`/diff tool will not map files to history. |
| Applied order differs from numeric order | Yes: `0023_llm_usage_v2` was applied before `0020_rag_v2`, and `0024` before `0021`. The migrations do not depend on each other in the swapped pairs (0023 only touches `llm_usage`/`record_llm_usage`), so replay in numeric order is safe by reading. **Not proven** (no fresh-database replay was run; see finding M-03). |
| Applied version timestamps | `20260930...` to `20261003212446` (0029 last). 0028 and 0029 are applied. |

### 2.2 Tables and columns

All 17 public tables exist and every column matches the migrations in type, nullability and default (checked column by column from `information_schema.columns`).

| Table | Expected columns (type / null / default) | Live | Verdict |
|---|---|---|---|
| profiles | id uuid PK -> auth.users cascade; full_name text; created_at timestamptz default now() | same | OK |
| roles | user_id uuid PK -> profiles cascade; role role_type not null default 'user' | same | OK |
| admin_permissions | id, admin_id, permission_key not null, granted_by, created_at | same | OK (columns) / **drift: duplicate unique constraint, see 2.4** |
| provider_keys | id, user_id, provider provider_name, slot key_slot, encrypted_key, is_valid default false, last_validated_at, created_at; unique(user_id,provider,slot) | same | OK |
| resumes | id, user_id, file_key, parsed_text, created_at, digest, content_hash, embed_version, display_name (embedding dropped by 0013) | same (position 5 is the dropped `embedding`) | OK |
| resume_chunks | id, resume_id, chunk_index, content, embedding vector(768), created_at, section, embed_version not null default 'legacy', content_tsv generated stored `to_tsvector('english', content)` | same | OK |
| interviews | 16 columns incl. running_summary, selected_question_ids uuid[] default '{}', current_question_index default 0, provider not null default 'gemini', brief, summarized_through_turn not null default 0 | same | OK |
| interview_transcripts | id, interview_id, turn_index, speaker, text, created_at | same | OK |
| question_bank | id, type, question, test_cases, tags, embedding vector(768), created_by, created_at, embed_version, difficulty smallint 1..5, topic, solution_code, solution_language | same | OK |
| interview_reports | id, interview_id not null, report_data not null, created_at, expires_at not null default now()+7d, user_id not null, overall_score smallint 0..100 not null, interview_type not null | same | OK |
| notifications | id, user_id, message, is_read default false, created_at | same | OK |
| conversations / chat_messages | as 0012 | same | OK |
| llm_usage | PK (user_id, provider, kind, day), requests, input_tokens, output_tokens, thought_tokens (0023) | same | OK |
| jobs | 12 columns as 0022 | same | OK |
| code_submissions | 11 columns as 0026 | same | OK |
| ats_scores | 9 columns as 0028 | same | OK |

Nullable-but-should-not-be (design looseness carried from the first draft, present live exactly as migrated): `admin_permissions.admin_id`, `provider_keys.user_id`, `resumes.user_id`, `interviews.user_id`, `interview_transcripts.interview_id`, `conversations.user_id`, `chat_messages.conversation_id`, `notifications.user_id`, `resume_chunks.resume_id`. All are protected by RLS/ownership checks (a NULL owner is invisible to everyone and the check constraint on `resumes.file_key` passes NULL but RLS `with check (user_id = auth.uid())` rejects it), so this is hygiene only (LOW L-06).

### 2.3 Constraints

| Constraint | Expected | Live | Verdict |
|---|---|---|---|
| FK cascades | profiles->auth.users CASCADE; every user_id FK CASCADE; resumes->resume_chunks, ats_scores CASCADE; interviews->transcripts, code_submissions, reports CASCADE; conversations->messages CASCADE; interviews.resume_id SET NULL (0019); code_submissions.question_id SET NULL; admin_permissions.granted_by and question_bank.created_by NO ACTION | identical | OK (but see M-01 for the two NO ACTION FKs) |
| `interview_transcripts_interview_turn_uq` unique (interview_id, turn_index) | present as unique index | OK |
| `jobs_one_active_per_kind` partial unique (user_id, kind) where status in ('queued','running') | present, predicate identical | OK |
| `code_submissions_one_per_problem` partial unique (interview_id, question_id) where status <> 'failed' | present | OK |
| `interview_reports_one_per_interview` unique(interview_id) | present | OK |
| `resumes_file_key_own_folder` CHECK | present: `file_key LIKE 'resumes/'||user_id||'/%' AND file_key NOT LIKE '%..%'` | OK |
| `resumes_display_name_check` 1..80 | present | OK |
| `ats_scores_composite_score_check` 0..100 | present | OK |
| `interview_reports_overall_score_check` 0..100 | present | OK |
| `code_submissions` checks: language 1..30, code 1..8000, line_count >=1, status in (review, done, failed) | present | OK |
| `jobs` checks: kind 1..40, status set | present | OK |
| `llm_usage_kind_check` chat/embed | present | OK |
| `question_bank_difficulty_check` 1..5 | present | OK |
| `admin_permissions` unique (admin_id, permission_key) | **present twice**: `admin_permissions_admin_permission_uq` (0019) and `admin_permissions_admin_key_unique` (0021) | **Drift (self-inflicted): duplicate constraint + duplicate index.** Advisor WARN `duplicate_index`. Fix: `alter table admin_permissions drop constraint admin_permissions_admin_key_unique;` |
| 3-resume limit | trigger only (no declarative constraint possible) | `resumes_limit_before_insert` BEFORE INSERT FOR EACH ROW -> `enforce_resume_limit()` (security definer, search_path=public, advisory lock per user) | OK |

### 2.4 Indexes

Every index in 0009, 0011, 0012, 0013, 0019, 0020, 0022, 0026, 0027, 0028 exists with the expected definition (`idx_resume_chunks_tsv` is GIN on `content_tsv`). Findings:

| Item | Detail | Verdict |
|---|---|---|
| Duplicate | `admin_permissions_admin_key_unique` = `admin_permissions_admin_permission_uq` (identical) | drop one (L-02) |
| Redundant prefix | `idx_admin_permissions_admin_id` is a prefix of the unique index (admin_id, permission_key); `idx_interview_transcripts_interview_id` is a prefix of `interview_transcripts_interview_turn_uq`; `idx_interview_reports_interview_id` duplicates `interview_reports_one_per_interview` (unique on the same column) | drop all three (L-02); the advisor lists two of them as "unused" |
| Missing FK index | `code_submissions.user_id` and `code_submissions.question_id` (advisor INFO `unindexed_foreign_keys`). `question_id` matters: deleting a question (SET NULL) scans code_submissions; `user_id` matters on user deletion (cascade) | add both (L-03); tiny tables today |
| Other FK columns | all remaining FK columns are covered (jobs.user_id by `jobs_user_created_idx`, llm_usage/provider_keys by their PK/unique prefix, ats_scores both) | OK |
| Vector indexes | none on `resume_chunks.embedding` or `question_bank.embedding` | intentional (PILLARS D3: exact scan; revisit at about 10k questions) |
| Frequent filters/order-bys in `app/db/*` | `interviews (user_id, created_at desc)` served by `idx_interviews_user_id` + small sort; `conversations (user_id, created_at)` same; `chat_messages (conversation_id, created_at)` served by `idx_chat_messages_conversation_id` + sort; `notifications (user_id, created_at desc)` same; `question_bank (type, created_at desc)` seq scan (small); `llm_usage` PK | OK at current scale; composite indexes would be a later optimisation |

### 2.5 Functions

| Function | Expected | Live | Verdict |
|---|---|---|---|
| private.is_owner(uuid) | SQL, SECURITY DEFINER, stable, search_path=pg_catalog, public; EXECUTE to authenticated (0008) | identical; ACL `postgres, authenticated` | OK |
| private.has_admin_permission(uuid,text) | same | identical | OK |
| private.handle_new_profile() | plpgsql SECURITY DEFINER, advisory lock (0019), search_path pg_catalog, public | identical; ACL null (default PUBLIC execute, but schema `private` has no USAGE for anon/authenticated listed beyond what the policies need and is not an exposed API schema) | OK |
| append_interview_turns(uuid,uuid,text,text) | SECURITY DEFINER, search_path=public, EXECUTE service_role only | identical, ACL `postgres, service_role` | OK |
| append_chat_exchange(uuid,uuid,text,text,text) | same | identical | OK |
| record_ats_score(uuid,uuid,text,text,text,int,jsonb,int) | same | identical | OK |
| enforce_resume_limit() | SECURITY DEFINER trigger fn, public/anon/authenticated revoked (0029) | ACL `postgres, service_role` | OK |
| record_llm_usage(8 args incl. p_thought, p_day) | invoker, search_path public, pg_catalog; service_role only; old 6-arg version dropped | exactly one overload (8 args), ACL postgres+service_role | OK |
| replace_resume_chunks, match_resume_chunks_multi, match_question_bank_v2 | invoker, search_path public, extensions, pg_catalog; service_role only | identical | OK |
| match_resume_chunks / match_question_bank (legacy) | dropped by 0024 | absent | OK |
| Stray functions | none in public/private beyond the above | OK |

SECURITY DEFINER functions (all pin `search_path`, all owned by `postgres`, none executable by anon/authenticated except the two RLS helpers in the non-exposed `private` schema): 7 total. No definer function is callable through PostgREST.

### 2.6 Triggers, extensions, RLS flags, policies

| Item | Result |
|---|---|
| Triggers (non-internal, public) | `on_profile_created` AFTER INSERT on profiles; `resumes_limit_before_insert` BEFORE INSERT on resumes. Both match. OK |
| Extensions | vector 0.8.2 in `extensions` (0007), plpgsql, pg_stat_statements, uuid-ossp, pgcrypto, supabase_vault. No pg_cron (plan said optional). OK |
| RLS enabled | true on all 17 tables, none forced. Matches. OK |
| Policies | 25 policies, text identical to the migrations incl. `(select auth.uid())` wrapping on every one. 4 tables have RLS and zero policies by design (`jobs`, `code_submissions`, `interview_reports`, `ats_scores`). OK |
| Policy role target | all policies are `TO public` (default). Harmless because `anon` has no table privileges at all. OK |

### 2.7 Grants (table and column level)

| Table | anon | authenticated (live) | service_role | Matches migrations? |
|---|---|---|---|---|
| all 17 | none | see below | all | anon: yes (0019 `revoke all ... from anon` plus explicit revokes later) |
| provider_keys | none | SELECT only on 7 columns (no `encrypted_key`); REFERENCES/TRIGGER/TRUNCATE table-level | all | yes (0019) |
| interviews, interview_transcripts | none | SELECT (+ REFERENCES, TRIGGER, TRUNCATE) | all | yes (0019) |
| resumes | none | SELECT; DELETE; INSERT on (id, user_id, file_key); UPDATE on (display_name) | all | yes (0028) |
| question_bank, jobs, code_submissions, interview_reports, ats_scores | none | **none** | all | yes (0020/0022/0026/0027/0028) |
| profiles, roles, admin_permissions, conversations, chat_messages, notifications, resume_chunks, llm_usage | none | ALL privileges (RLS limits rows) | all | yes, but wider than the app needs: see H-01 |

Default privileges (`pg_default_acl`) still grant every future table/function/sequence in `public` to anon/authenticated/service_role. Every migration so far revoked explicitly; a future table that forgets to will be exposed (L-05).

### 2.8 Storage

`storage.buckets`: one bucket `resumes`, `public=false`, `file_size_limit=512000` (500 KB), allowed types PDF and DOCX only. `storage.objects` has **no policies**, so the anon and authenticated roles cannot read or write objects through the Storage API; all access is through the S3 endpoint with the project's S3 access key (server side: Next route handler and FastAPI). That is a sound, minimal configuration. Live: 1 object (142,831 bytes).

### 2.9 Live data snapshot (counts only)

1 auth user, 1 profile, 1 role, 1 resume (processed, 7 chunks), 2 conversations, 9 messages, 1 provider key, 2 llm_usage rows, **0 interviews, 0 transcripts, 0 reports, 0 jobs, 0 ats_scores, 0 code_submissions, 0 question_bank rows**. Database size 12 MB. This means: interviews, coding round, reports, ATS (incl. history) and the question bank have never produced a row on the live database; they are verified only by mocks. `question_bank` being empty means coding/webd/sde interviews have no problems to ask until `scripts/load_starter_questions.py` is run.

---

## 3. Code vs schema contract

Every database access in the API lives in `apps/api/app/db/*.py` (enforced by `tests/test_architecture.py`; a grep for `.table(` / `.rpc(` outside `db/` returns nothing). The web app talks to Supabase directly from only these places: `lib/auth/guards.ts`, `app/auth/callback/route.ts`, `app/(auth)/*` (profiles), `app/api/resumes/*` (resumes), `components/ui/NotificationsBell.tsx`, `ChatListView.tsx`, `ChatThreadView.tsx`.

### 3.1 Backend (db layer)

| Module | Tables / RPCs / columns used | Exists live and types fit? |
|---|---|---|
| db/ats_history.py | rpc `record_ats_score` (8 named params), `ats_scores` select `id, resume_id, job_title, jd_excerpt, provider, composite_score, created_at, result` | yes; param names and types match (p_composite integer -> smallint check) |
| db/chat.py | `conversations(id,user_id,title,created_at)`, `chat_messages(id,role,provider,content,created_at)`, rpc `append_chat_exchange` (5 params) | yes |
| db/interviews.py | `interviews` (select *, insert user_id/type/jd_text/resume_id/provider/status, updates incl. status/phase/brief/...), `interview_transcripts`, rpc `append_interview_turns` (4 params) returns int, `question_bank.question` | yes |
| db/jobs.py | `jobs` (all columns), 23505 on the partial unique index | yes; error code handled (`getattr(exc,"code")=="23505"`) |
| db/keys.py | `provider_keys` upsert `on_conflict="user_id,provider,slot"` (matches the unique constraint), `notifications` insert | yes |
| db/maintenance.py | `resume_chunks.embed_version/embedding`, `question_bank.embed_version/embedding`, `provider_keys.encrypted_key` | yes (service role) |
| db/questions.py | `roles`, `admin_permissions`, `question_bank` incl. `test_cases, solution_code, solution_language`, rpc `match_question_bank_v2` (4 params; jsonb embedding) | yes |
| db/readiness.py | `profiles` select | yes |
| db/reports.py | `interview_reports(id, interview_id, interview_type, overall_score, created_at, expires_at, report_data, user_id)`, delete `expires_at < now`, 23505 handled | yes |
| db/resumes.py | `resumes` select(columns), rpc `replace_resume_chunks` (6 params), `resume_chunks` count, rpc `match_resume_chunks_multi` (4 params: filter_resume_id, query_embeddings, query_terms, per_query) | yes |
| db/submissions.py | `code_submissions` columns, 23505 handled | yes |
| db/team.py | `profiles`, `roles` upsert on `user_id`, `admin_permissions` delete+insert, `auth.admin.list_users(page=1, per_page=200)` | yes |
| db/usage.py | rpc `record_llm_usage` (params built in `llm/usage.py`), `llm_usage` select incl. `thought_tokens` | yes |

No column, table or RPC name used by the API is missing live; no type mismatch found.

### 3.2 Web (direct Supabase calls)

| Caller | Operation | Allowed by grants/RLS? |
|---|---|---|
| guards.ts | select profiles(id), provider_keys(id) where is_valid, roles(role), admin_permissions(permission_key) | yes (`is_valid` and `id` are in the provider_keys column grant) |
| account setup / demo sign-up | insert profiles(id, full_name) | yes (insert policy `id = auth.uid()`; trigger then writes `roles`) |
| /api/resumes POST | count resumes; insert (id, user_id, file_key) `.select()` (returning needs SELECT: granted); trigger error message contains `resume_limit` -> mapped to 409 | yes; insert column list equals the column grant |
| /api/resumes GET | select id, file_key, parsed_text, display_name, created_at | yes (note: sends full `parsed_text` of every resume to the browser to learn "processed or not": LOW L-08) |
| /api/resumes/[id] DELETE | select file_key; delete returning id | yes (delete privilege + owner policy) |
| /api/resumes/[id] PATCH | update display_name returning id, display_name | yes (UPDATE only on display_name) |
| NotificationsBell | select notifications; update is_read | yes |
| ChatListView | delete conversations (messages cascade) | yes |
| ChatThreadView | select conversations.title | yes |

### 3.3 Constraints the code relies on, and error handling

| Reliance | Exists live | Code handling | Verdict |
|---|---|---|---|
| One active job per user+kind | yes (partial unique) | `create_job` returns None on 23505, caller returns the existing job | OK |
| One submission per problem | yes (partial unique, `status <> 'failed'`) | `create_submission` returns None on 23505 | OK. Note: rows whose `question_id` became NULL (question deleted) never conflict; cannot happen for a new submission (question_id is required) |
| One report per interview | yes (unique) | `save_report` deletes then inserts; 23505 on a race returns the existing report | OK |
| 3-resume trigger (P0001, message `resume_limit: ...`) | yes | web maps by message substring; API never inserts resumes | OK |
| `file_key` own-folder CHECK (23514) | yes | web builds `resumes/<uid>/<uuid>.<ext>`; a violating insert would surface as 500 with the DB message | OK (unreachable from the UI) |
| composite_score / overall_score ranges (23514) | yes | scores clamped in code before insert | OK |
| code/language length checks | yes (8000 / 30) | request model caps at the same numbers (`MAX_CODE_CHARS=8000`, `max_length=30`) | OK. Doc says 6,000 (PHASE7_PLAN): stale doc |
| P0002 ("not found" raised by `append_*`, `record_ats_score`, `replace_resume_chunks`) | yes | callers verify ownership first; the RPC's own P0002 is not mapped, so a race (row deleted between check and RPC) would surface as a generic 500 through the catch-all | LOW (L-07) |
| 23503 FK violations | `interviews.resume_id` etc. | resume delete is safe (SET NULL); question delete is safe; **deleting a user who granted permissions or created questions fails** (M-01) | see M-01 |
| 22P02 invalid uuid | uuid columns | routers type path params as `UuidStr` | OK |
| 42501 permission denied | client roles | the web only performs operations in 3.2 which are granted; a revoked write would 403 from PostgREST | OK |
| Chat ordering by `created_at` | `append_chat_exchange` uses `clock_timestamp()` +1 ms | read orders by `created_at` only (no id tie-break), fine with the 1 ms offset | OK |
| Turn ordering | unique (interview_id, turn_index) + row lock in RPC | OK |
| `provider_keys.upsert on_conflict` | unique (user_id, provider, slot) | OK |
| `jobs` stale recovery | no DB support needed | `fail_all_active` on boot | OK (see M-04) |

---

## 4. Database security matrix

Legend: R/W = row-level via the policy named; "backend only" = RLS on, no policy, no client privilege.

| Table | RLS | Policies | authenticated can | anon | Reachable data / notes | Verdict |
|---|---|---|---|---|---|---|
| profiles | on | select/insert/update own (`id = (select auth.uid())`) | select, insert, update own row (any column, text unbounded) | none | own name only | OK; write grant wider than needed (H-01) |
| roles | on | select own or owner; insert/update/delete owner only | owner can change any role, including their own, via the API | none | role leak: only own row (owner sees all) | OK for tenants; no "last owner" guard in DB (L-04) |
| admin_permissions | on | select own/owner; write owner only | owner writes | none | | OK; two identical unique constraints (L-02) |
| provider_keys | on | owner `for all` | **select on 7 non-secret columns only**; no insert/update/delete | none | `encrypted_key` unreachable by clients | OK (strong) |
| resumes | on | owner `for all` | select all columns (incl. `parsed_text`, `digest`), delete, insert (id,user_id,file_key), update (display_name) | none | own rows; forged other-user key blocked by CHECK; limit trigger | OK |
| resume_chunks | on | owner via parent | **full DML on own chunks** (content, embedding, any size) | none | | H-01: client can bypass the pipeline and bloat DB; no cross-user risk |
| interviews | on | owner `for all` | select only | none | `jd_text`, brief, running_summary are readable by the owner (their own data) | OK |
| interview_transcripts | on | owner via parent | select only | none | | OK |
| question_bank | on | select_all (any signed-in), write = permission | **no privileges** (revoked 0020) | none | reference solutions unreachable | OK now; the dead `select_all` policy would re-expose solutions if SELECT were ever re-granted (L-01) |
| interview_reports | on | none | none | none | backend only; 7-day expiry enforced in code | OK |
| jobs | on | none | none | none | backend only | OK |
| code_submissions | on | none | none | none | verdicts hidden from candidates | OK |
| ats_scores | on | none | none | none | | OK |
| notifications | on | select/update own | full DML on own rows (RLS: select/update only; insert/delete blocked) | none | can edit own message text | OK (LOW) |
| conversations | on | owner `for all` | **insert/update/delete own, unbounded** | none | web needs only delete | H-01 |
| chat_messages | on | owner via parent | **insert/update/delete own, unbounded; can forge assistant messages** | none | web never writes here | H-01 |
| llm_usage | on | select own | RLS blocks writes (no write policy) though table privileges are ALL | none | | OK (privileges wider than needed) |

Other checks:

* **TRUNCATE/REFERENCES/TRIGGER** are held by `authenticated` on all tables that keep Supabase default grants. PostgREST does not expose TRUNCATE, so this is not exploitable through the API; it matters only if a direct SQL role is ever handed to a client. Revoke for defence in depth (L-05).
* **SECURITY DEFINER inventory**: 7 functions (see 2.5); owner `postgres`; every one has `set search_path`; EXECUTE revoked from public/anon/authenticated except `private.is_owner` and `private.has_admin_permission` (needed by policy evaluation; schema `private` is not an exposed schema, ACL on `private` namespace is null so only its owner and explicit grants can use it).
* **Backend-only tables really unreachable?** Yes for jobs, code_submissions, interview_reports, ats_scores, question_bank: zero grants to anon/authenticated and RLS without policies.
* **Cascades on deletes**: deleting a *user* (auth.users) cascades to everything except `admin_permissions.granted_by` and `question_bank.created_by` (NO ACTION: **blocks the delete**, M-01) and to nothing in Storage (the user's `resumes/<uid>/...` objects are orphaned, L-09). Deleting a *resume* cascades chunks and ATS history, nulls `interviews.resume_id`; the web route deletes the storage object afterwards (failure only logged). Deleting an *interview* cascades transcripts, submissions, report. Deleting a *conversation* cascades messages. Deleting a *question* nulls `code_submissions.question_id`; `interviews.selected_question_ids` (uuid[] without FK) keeps stale ids, which the code tolerates (`question_text` returns None).
* **Orphan risks**: storage objects after user deletion or after a failed storage delete; stale ids in `selected_question_ids`.
* **Realtime**: publication `supabase_realtime` exists with no tables.
* **Auth-side** (not inspectable via SQL): "leaked password protection" is off (advisor); whether email signups/confirmation are enabled is not visible here (needs verification, matters while the demo sign-up exists).

---

## 5. Advisor results explained

Security advisor (2 lints):

| Lint | Level | Detail | Intentional or real? |
|---|---|---|---|
| `rls_enabled_no_policy` | INFO | `ats_scores`, `code_submissions`, `interview_reports`, `jobs` have RLS and no policy | **Intentional.** Backend-only tables: RLS on + no policy + no client grants = deny all for anon/authenticated; service role bypasses RLS. Could be silenced with a comment/explicit deny policy. |
| `auth_leaked_password_protection` | WARN | HaveIBeenPwned check disabled | **Real but low impact today** (passwords exist only as an alternate login and in the temporary demo sign-up). Dashboard toggle; may need a paid plan. On the launch checklist. |

Performance advisor (3 lints):

| Lint | Level | Detail | Verdict |
|---|---|---|---|
| `unindexed_foreign_keys` | INFO | `code_submissions.question_id`, `code_submissions.user_id` | **Real, trivial.** Add two indexes (L-03). |
| `unused_index` | INFO | 12 indexes never used: admin_permissions (2), interview_reports (2), interview_transcripts_interview_id, interviews_resume_id, question_bank_created_by, resume_chunks_tsv, jobs_user_created_idx, ats_scores (2), code_submissions_interview_idx | **Mostly noise**: the database has almost no traffic (12 MB, 0 interviews), so nothing has had a chance to use them. Exceptions that are truly redundant (not just unused): `idx_admin_permissions_admin_id`, `idx_interview_transcripts_interview_id`, `idx_interview_reports_interview_id` (see 2.4). Keep the rest; re-check after real traffic. |
| `duplicate_index` | WARN | `admin_permissions_admin_key_unique` = `admin_permissions_admin_permission_uq` | **Real**, created by 0019 + 0021 both adding the same unique constraint (L-02). |

Advisors do **not** flag: mutable search_path, exposed SECURITY DEFINER functions, RLS disabled, policy initplan, multiple permissive policies. Those were all fixed earlier (0007/0009/0019/0020).

---

## 6. Docs vs reality: corrections list

Every doc was read in full. Test counts and states below were verified on 2026-10-04: backend `pytest` = **605 passed, 1 skipped** (the skip is `test_recorded_fixtures`, because `tests/fixtures/` does not exist: no live responses were ever recorded); frontend `vitest` = **158 passed in 24 files**; live schema = 17 tables, migrations 0001-0029 applied.

### 6.1 docs/PRODUCT.md (meant to be the single A-Z reference; it is a 2026-10-02 snapshot and has not been touched since commit `b841c82`, i.e. before about 40 commits)

| Section | Wrong or stale text | Correct text |
|---|---|---|
| Header | "Snapshot date 2026-10-02 ... 31 commits"; companion files list only IMPLEMENTATION, DOCUMENTARY, PILLARS_PLAN | Snapshot 2026-10-04, 74 commits; companions also FACTS.md, PHASE7-10_PLAN.md, UI_REFRESH.md, FRONTEND_GAPS.md, audit/*.md |
| 1 (services table) | Interviewing agent: "text mode built; coding platform, voice, reports planned" | Text, coding round (reference-solution review, nothing executed), browser voice and 7-day reports are all built; none has run on the live database (0 interviews, 0 reports) |
| 1 | ATS: "needs R2 to run live" | Storage is Supabase Storage (S3 API), already live (1 resume uploaded and processed); ATS scoring itself still not exercised live (0 ats_scores rows) |
| 2.1 | "Team management page ... stub page only" | Built: `/settings/team`, API `GET /team/users`, `PATCH /team/users/{id}/role`, `PUT /team/users/{id}/permissions`; Owner-only, the only permission today is `manage_question_bank` |
| 2.2 | "notifications are written; nothing displays them yet"; "Delete a key from the UI: planned" | Notifications bell is built; key delete UI is built (with a Gemini-primary warning) |
| 2.3 | "History window (last 10 messages, <=2,000 tokens)"; "Rename/delete conversation, titles: planned" | Window 10 messages, 3,000-token budget (`chat/service.py`); rename (`PATCH /chat/conversations/{id}`) and delete (direct, RLS) are built |
| 2.4 | "Upload PDF/DOCX (<=5 MB) to private Cloudflare R2 ... R2 credentials not yet configured" | <=500 KB (web `route.ts`, API `_MAX_FILE_BYTES`, bucket limit 512000), private **Supabase Storage** bucket `resumes` via the S3 API; max **3 resumes per user** (UI pre-check plus DB trigger); rename (`display_name`); live-verified upload and processing |
| 2.5 | "No history stored (decision) - by design" | Superseded 2026-10-04: last **10** checks per resume are stored in `ats_scores` (migration 0028), listed/opened/deleted via `GET/DELETE /ats/history` and the "Previous checks" panel |
| 2.6 | "Polished ~5-minute setting up screen ... planned (currently synchronous)" | Setup is a polled background job (`jobs`) with progress text and a Cancel button (`POST /interviews/{id}/abort`) |
| 2.6 | "Question bank admin: create/edit/delete with test cases and tags" | Form holds question, **reference solution + language**, tags, topic, difficulty; test cases are no longer entered (column kept, unused); solutions never reach candidates |
| 2.6 | Coding round "awaiting migration 0026"; Report "awaiting migration 0027" | Both applied 2026-10-03; still unverified live |
| 2.6 | missing | Delete an interview (cascades transcript, code, report); abort setup; one submit per problem; browser voice details |
| 2.7 | "Accessibility pass, reduced motion, error-state sweep: planned Phase 10" | Reduced-motion support, skip link, in-app ConfirmDialog/Toast, labelled controls and retry states are built (UI_REFRESH.md, FRONTEND_GAPS.md); screen-reader testing not done |
| 3 (diagram, stack) | "Cloudflare R2 (resumes, later reports)"; "(planned) coding (Judge0), voice, reports, jobs"; "Storage: Cloudflare R2 ... not yet configured"; "Code execution (planned): Judge0" | Supabase Storage (1 GB free); coding/jobs/reports/team exist; voice is browser-side only; **no code is ever executed** (Judge0 plan withdrawn 2026-10-03) |
| 3 (tests row) | "504 passing + 2 strict known-bug markers" | 605 backend tests pass + 1 skipped; 158 frontend tests (vitest); tsc, eslint, next build clean |
| 3.1 repo map | `sign-up(demo)`, "reports(stub)", "settings/team(stub)", "coding[empty] reports[empty] voice[empty]", "migrations/0001-0019", docs list | Reports and team pages exist; `apps/api/app/{coding,reports,team,jobs,db}` and `core/jobs.py` exist; voice lives in `apps/web/lib/voice`; migrations 0001-0029; docs folder has 11 files plus `audit/` |
| 3.2 HTTP API | Lists only keys/chat/rag/ats-score/interviews/usage | Add: `GET /ready`; `PATCH /chat/conversations/{id}`; `GET /ats/history`, `GET|DELETE /ats/history/{id}`; `POST /interviews/{id}/abort`, `DELETE /interviews/{id}`; `GET /interviews/{id}/problem`, `POST /interviews/{id}/submissions` (6/min); `GET /jobs/{id}`; `POST /interviews/{id}/report` (3/min), `GET /reports`, `GET|DELETE /reports/{interview_id}`; `/team/*`. Next handlers: add `PATCH /api/resumes/{id}`. The authoritative list is `apps/api/tests/openapi_snapshot.json` |
| 3.3 data model | "live, 14 tables"; "interview_reports (unused yet)"; "Migrations 0001-0018 applied; 0019 applied" | 17 tables (+`jobs`, `code_submissions`, `ats_scores`); reports are backend-only and used; migrations 0001-0029 applied; add the 7 functions and the 2 triggers |
| 4 (How things work) | Resume upload "Browser -> Next route -> R2"; interview "Start" described as synchronous | Storage is Supabase; start is a job (`interview_setup`) polled by the page; add the code-review job and report job flows |
| 5 decisions | #5 "ATS: no history persisted"; #10 "Supabase Storage replaced by R2 ... Judge0 hosted"; #7 "test cases are an answer key" | #5 reversed (last 10 kept). #10 reversed: Supabase Storage again; Judge0 withdrawn. #7: now reference solutions. Add: no code execution; browser voice instead of Gemini Live; reports on demand with print-to-PDF/text; 500 KB resume cap; 3 resumes |
| 6 (chronology) | Ends at "M0 safety net" on 10-02 | Add 10-03 (storage switch, 500 KB, M4 jobs/atomicity, phases 7-10, migrations 0021-0027) and 10-04 (project audit, UI refresh, frontend rounds 2-3, migrations 0028-0029). The quality-gates sentence ("504 backend tests ... nothing about R2 ... ran against real services") is stale |
| 7 | "Built but unverified live: resume upload/processing"; "Credentials: ... no R2"; "Open items: notifications and key-delete UI"; "Known weaknesses being addressed by the pillars plan" | Resume upload and processing are verified live; storage credentials are Supabase S3 keys; those UI items are done; every listed weakness was addressed by M0-M4 |
| 8 | Entire section ("Proposed plan awaiting approval", M4 pending, Phase 7 Judge0, Phase 8 Live API, Phase 9 pg_cron, "Decisions still needed") | Replace with: M0-M4 done; phases 7-9 done as redesigned (see section 7); phase 10 partly done; remaining: Dockerfile, render.yaml, DEPLOY.md, check_deploy.py, LAUNCH_CHECKLIST.md, real-Postgres CI tests, Playwright smoke |
| 9 | Judge0 facts | Keep as history; add Supabase free-tier facts (500 MB DB, 1 GB storage, project pauses after a week of inactivity) |
| 10 | "504 passed, 1 skipped, 2 xfailed"; web commands only tsc/eslint/build | `605 passed, 1 skipped`; add `npm test` (vitest, 158) |

### 6.2 Other docs

| File | Statement | Problem / correction |
|---|---|---|
| IMPLEMENTATION.md | Section 11 "Planning complete. Awaiting explicit approval"; stack table (R2, Judge0, Python 3.11, apscheduler, websockets, zustand, zod); Phase 7 Judge0, Phase 8 WebSocket voice, Phase 9 apscheduler; "ATS checks are not persisted" | PRODUCT calls it the "original fixed plan" but the file has no banner. Section 6 was partly updated, so it is half old, half new. Add a "historical, superseded by PRODUCT.md" banner. |
| PILLARS_PLAN.md | Status line "Phase 7 (coding platform) is next, after the execution-backend decision"; migration batches table names (`0023_llm_observability`, `0024_coding`, `0025_reports`); `llm_usage.feature/model`, `chat_messages.status`, prompt-version columns, `test_results`; D8 presigned R2; D6 `google-genai` migration | Real files: 0023_llm_usage_v2, 0024_drop_legacy_retrieval, 0026_coding, 0027_reports. `llm_usage.feature/model`, `chat_messages.status`, prompt-version columns and `test_results` were **never built** (the live schema confirms) and are not marked dropped. D8 and the async-client item are noted as dropped inside the M4 bullets only. The google-genai migration is obsolete (REST adapter). Add an outcome table. |
| PHASE7_PLAN.md | status "migration 0026 awaits go-ahead"; "Code capped at 6,000 characters"; code_submissions column list | 0026 applied 10-03; cap is **8,000** (code, DB check and request model); the table also has `summary` and `line_count` |
| PHASE8_PLAN.md | "Needed from the owner" items open | Built; still awaiting hands-on test (accurate) |
| PHASE9_PLAN.md | status "migration 0027 awaits go-ahead" | applied 10-03 |
| PHASE10_PLAN.md | "573 backend tests and 19 frontend tests pass; Migrations 0001-0027 are live"; references `docs/DEPLOY.md`, `docs/LAUNCH_CHECKLIST.md`, `scripts/check_deploy.py`, Dockerfile, render.yaml, `.dockerignore`, Playwright | Numbers now 605 / 158 and 0001-0029. None of the referenced deployment files exist (the status line says deployment is set aside, so this is accurate; see section 11). Real-Postgres CI tests: not built. |
| FACTS.md | `google-generativeai` deprecation note; Judge0 section; "Not yet measured" list | The adapter is REST so the SDK note is obsolete; Judge0 plan withdrawn; the "assumed from documentation" and "not yet measured" lists are still true (no `tests/fixtures/gemini`, so `llm_smoke --record` was never run). Add Supabase Storage/free-tier facts and the Chrome speech-recognition facts. |
| PROJECT_DOCUMENTARY.md | "STATE SNAPSHOT -- read this first when resuming" (2026-10-02): 122 tests, "Phases 7-10 not started", "0018 pending", "R2 not set up" | Dangerously stale as a "read first". Mark it superseded or replace it with a current snapshot. Every build step has an entry (checked: planning, phases 1-6, live run, LLM architecture 1-6, audits, M0-M4, storage switch, 500 KB, phase 7-10 plans and builds, 10-04 audit, UI refresh, round 2, 0028/0029, round 3). **Gaps**: the migration `fix_remaining_rls_initplan` (applied live 2026-09-30) has no entry of its own; nothing records that 0023 and 0024 were applied before 0020 and 0021; the redundant duplicate unique constraint from 0021 is not mentioned. |
| FRONTEND_GAPS.md | G12 "server-side enforcement only in the Next handler, see B07"; G30 | Consistent after round 3. Fine. |
| UI_REFRESH.md | "vitest 19" in the round-1 changelog | Correct for that round; final count is 158. Fine. |
| apps/web/README.md | create-next-app boilerplate | Replace with real run/test/env instructions. There is **no root README.md**, no `.env.example` for the web app, no runbook. |
| apps/api/.env.example | SUPABASE_*, KEY_ENCRYPTION_SECRET, STORAGE_*, ENVIRONMENT, CORS_ORIGINS | Complete for the server; the scripts' `GEMINI_API_KEY`, `GROQ_API_KEY`, `ANTHROPIC_API_KEY` are documented only in script docstrings. |

### 6.3 FACTS.md items vs what the code assumes

| FACTS item | Code assumption | Match? |
|---|---|---|
| Gemini quotas per project, reset midnight Pacific | `keystate.py` Pacific quota day; usage booked with `p_day` | yes |
| embedding-001: 768 dims need manual normalisation, 2,048 input tokens, task types | `EMBEDDING_DIMENSIONS=768`, L2-normalise in `llm/`, `EMBEDDING_VERSION="gemini-embedding-001:768:v2"` | yes |
| Thinking default-on for 3.x lite | `thinkingLevel: minimal` for `gemini-flash-lite-latest`, auto-dropped if rejected | assumed, unverified (FACTS says so) |
| Claude IDs | `_CLAUDE_STRONG = "claude-sonnet-5-5"` | yes |
| Groq IDs | 8B instant / 70B versatile | yes |
| Live API / Judge0 | not used | obsolete facts |
| Real 429/503 bodies | parsed defensively (`quotaId` contains PerDay/PerMinute) | unverified until the smoke script is run |
| Plan said "replace `-latest` with pinned IDs" | `_GEMINI = "gemini-flash-lite-latest"` still an alias | **not done** (M-05) |

### 6.4 Missing documentation (nothing describes these)

Team management; ATS history; reports (flow, 7-day rule, sweep); browser voice (browser support, privacy note); coding round (one submit, review-only); `scripts/rotate_keys.py` procedure (docstring only); the OpenAPI snapshot workflow (docstring only); jobs and stale recovery (STALE_AFTER 420 s); the `jobs`, `ats_scores`, `code_submissions` tables; throttle limits per endpoint; a first-time setup runbook (create Supabase project, apply migrations, create the bucket with the 500 KB and MIME limits, S3 key, Google OAuth, first Owner); how to run the owner-run scripts (order, quota cost); a root README.

---

## 7. Feature and plan checklist

Status key: **LIVE** = built and observed working on the real stack; **BUILT** = built, automated tests only, never run against live services (the live database has 0 rows for it); **PARTLY**; **MISSING**; **DROPPED** = deliberately not built (decision recorded). Evidence of "live" comes from the live database (rows present) and the documentary's own live-run entries. Nothing here was exercised by this audit (no provider calls).

### 7.1 Product features (PRODUCT.md section 2)

| Feature | Status | Evidence |
|---|---|---|
| Google sign-in, account setup, profile + role trigger, first user Owner | LIVE | 1 auth user, 1 profile, 1 role row; `app/(auth)/*`, `private.handle_new_profile` |
| Route guards, role/permission helpers | LIVE | `lib/auth/guards.ts` |
| Backend JWT verification (ES256 JWKS, HS256 fallback) | LIVE | `core/security.py`; documentary 10-02 first live run |
| Temporary demo email/password sign-up | BUILT, **must be deleted before launch** | `app/(auth)/sign-up/DemoSignUpView.tsx` still tracked and linked |
| Team management (Owner promotes admins, grants permissions) | BUILT | `app/(dashboard)/settings/team/*`, `app/team/*`, `db/team.py`; 0 admin_permissions rows |
| BYOK keys (Gemini/Claude/Groq, primary+backup, Fernet, validation, delete UI, "Used today") | LIVE for Gemini (1 provider_keys row, 2 llm_usage rows); Claude and Groq BUILT | `keys/*`, `providers/*`, `llm_usage` rows |
| Silent failover + notification + bell | BUILT | `llm/gateway.py`, `NotificationsBell.tsx`; 0 notifications rows |
| Chat (list, thread, streaming, provider selector, rename, delete, copy) | LIVE (Gemini) | 2 conversations, 9 messages; rename/delete added 10-04, not yet used |
| Resume upload (PDF/DOCX, 500 KB, 3-resume limit, rename), processing, digest, retry, delete | LIVE (upload + processing: 1 resume, 7 chunks, 1 storage object); rename and limit trigger verified in a rolled-back transaction per the documentary | `app/api/resumes/*`, `rag/*`, 0028 |
| ATS score (keywords + semantic + formatting, feedback) | BUILT | `ats/*`; 0 ats_scores rows; calibration constants await owner-run `rag_eval_live.py` |
| ATS history (last 10 per resume, open/delete) | BUILT | `db/ats_history.py`, `AtsHistoryPanel.tsx`, `ats_scores` |
| Interview setup as a polled job with progress and Cancel | BUILT | `jobs`, `interviews/service.py`, `InterviewSetupView.tsx`; 0 jobs |
| 8 interview types, phases by elapsed time, turns, running summary | BUILT | `interviews/types/*`, `orchestrator.py`, `summarizer.py`; 0 interviews |
| Question selection (diverse, non-repeating) | BUILT, **cannot function until the bank is loaded** | `question_selection.py`; question_bank has 0 rows |
| Question bank admin (reference solutions, topic, difficulty) | BUILT | `admin/question-bank/*`; 0 rows; starter loader not yet run |
| Coding round (Monaco, one submit per problem, one LLM review, verdict hidden) | BUILT | `app/coding/*`, `CodeEditorPanel.tsx`, `code_submissions`; 0 rows; `judge_eval_live.py` not run |
| Voice (browser STT/TTS, endpointing, nudges, interruption option) | BUILT, awaiting hands-on test | `lib/voice/*`, `VoiceBar.tsx`, unit tests |
| Reports (one LLM call, verified quotes, computed score, 7 days, print/text export, delete) | BUILT | `app/reports/*`, `interview_reports`, `ReportDetailView.tsx`; 0 rows; `report_eval_live.py` not run |
| Interview abort / delete | BUILT | `POST /interviews/{id}/abort`, `DELETE /interviews/{id}` |
| Dark/light themes, motion, reduced motion, 3D loading scene, skeletons, dialogs/toasts | BUILT (visual checks done by agents in a preview browser; owner click-through pending) | UI_REFRESH.md |
| Privacy page | BUILT | `app/privacy/page.tsx` |
| Untimed practice mode | DROPPED (deferred) | PRODUCT 2.6 |
| Session recording | DROPPED (declined) | PRODUCT 2.6 |
| Anti-cheat | DROPPED (deferred) | PRODUCT 2.6 |

Headline: of 22 shipped feature rows, **4 are verified live** (auth/roles, BYOK Gemini, chat, resume upload and processing); **18 are built but never run on live data**. Dropped or deferred: 3.

### 7.2 Plan items

| Plan item | Status | Evidence / note |
|---|---|---|
| M0 safety net: 0019, startup validation, CORS/docs from env, CI, model IDs, FACTS.md, upload limit | done | `core/config.py`, `.github/workflows/ci.yml`, `docs/FACTS.md` |
| M1 platform core: error envelope, request ids, JSON logs, db layer + architecture test, waking-server UI, throttles, pagination | done | `core/errors.py`, `middleware.py`, `jsonlog.py`, `throttle.py`, `tests/test_architecture.py` |
| M2 LLM hardening (timeouts, typed errors, limiter, structured output, injection standard, Pacific day, fixtures, smoke script) | done except: pinned model IDs (still `-latest` alias), `llm_usage.feature/model` and prompt-version columns (never built, not marked dropped), recorded fixtures (never recorded) | `llm/*`, `scripts/llm_smoke.py` |
| M3 RAG v2 (eval harness, chunker v2, multi-term RPC, calibrated ATS, selection, lockdown, re-embed) | done; live calibration run not done | `tests/rag_eval/*`, `scripts/rag_eval_live.py`, `reembed.py` |
| M4 jobs + atomic RPCs | done (0021, 0022, 0025) | tables/functions verified live |
| M4 presigned direct-to-R2 upload | DROPPED 2026-10-03 | plan note |
| M4 async supabase client | DEFERRED | plan note |
| Phase 7 coding | done, redesigned (no execution, reference solution) | the withdrawn Judge0 `ExecutionBackend` and `test_results` are not built, by design |
| Phase 8 voice | done, redesigned (browser, no WebSocket/Live API/`google-genai`) | `lib/voice/*` |
| Phase 9 reports | done, redesigned (in-API sweep, no `pg_cron`, print-to-PDF, no presigned download) | `reports/service.py` `sweep_forever` |
| Phase 10.1 cleanup: unused backend deps removed, dev requirements split, MultiFernet + rotate script, `/ready` | done | `requirements*.txt`, `scripts/rotate_keys.py` |
| Phase 10.1 Dockerfile, `.dockerignore`, `render.yaml` | **MISSING** (set aside by owner) | no such files |
| Phase 10.1 `npm audit` / `pip-audit` pass | PARTLY | see section 10: 2 low prod npm advisories, dev-only highs, pip-audit not wired |
| Phase 10.2 OpenAPI snapshot test | done | `tests/test_openapi_snapshot.py`, `scripts/update_openapi_snapshot.py` |
| Phase 10.2 real-Postgres CI tests (RPCs, constraints, grants) | **MISSING** (owner decision pending) | none |
| Phase 10.3 polish: key delete, confirmations, bell, reduced motion, skip link, privacy | done | FRONTEND_GAPS.md |
| Phase 10.3 delete demo sign-up | deliberately kept until launch | on the launch checklist |
| Phase 10.3 Playwright smoke + axe scan | **MISSING** | none |
| Phase 10.4 `docs/DEPLOY.md`, `scripts/check_deploy.py`, Supabase redirect config, keep-warm | **MISSING** | none |
| Phase 10.5 `docs/LAUNCH_CHECKLIST.md` | **MISSING** | none (section 11.4 proposes one) |
| Frontend gap list G01-G32, B01-B08 | done and tested | FRONTEND_GAPS.md |
| Pending features (rename resume, 3-resume DB limit, ATS history, team, abort/delete interview, rename chat, clear fields) | done | 0028, 0029 |
| Deferred backlog | practice mode, anti-cheat, recording (declined), generated TS types from OpenAPI, HNSW at 10k questions, async client, `pg_cron`, Gemini Live voice | recorded in docs |

Promised but not delivered and not stated as dropped anywhere: `llm_usage.feature/model` columns, prompt-version stamping columns, `chat_messages.status`, recorded Gemini fixtures (`tests/fixtures/gemini/`), a pinned Gemini model, `docs/DEPLOY.md`, `docs/LAUNCH_CHECKLIST.md`, `.dockerignore`, `scripts/check_deploy.py`, a `last_verified` marker in `llm/models.py`.

---

## 8. CI and repo hygiene

### 8.1 Workflow `.github/workflows/ci.yml`

I replayed it from a **fresh `git clone`** of the repo in a scratch directory (new venv, `npm ci`, placeholder env vars exactly as in the workflow).

| Step | Result on a clean checkout |
|---|---|
| api: `pip install -r requirements-dev.txt` (Python 3.13.5) | OK |
| api: `python -m pytest -q` | **605 passed, 1 skipped** (no `.env`, no network needed: the autouse fixture forbids real Supabase) |
| web: `npm ci` (Node 22.13) | OK (warns that eslint 9.39.5 is "no longer supported") |
| web: **`npx tsc --noEmit`** | **FAILS**: `app/layout.tsx(24,50): error TS2304: Cannot find name 'LayoutProps'.` `LayoutProps` is a global type that Next generates into `.next/types` / `next-env.d.ts` (both gitignored). In the workflow `tsc` runs before `next build`, so on a clean runner the job is red at its first web step every time. Locally it passes only because `.next/` and `next-env.d.ts` exist. (H-02) |
| web: `npx eslint .` | OK (exit 0) |
| web: `npm test` (vitest) | OK, 24 files, 158 tests |
| web: `npx next build` | OK (21 routes); its own TypeScript pass succeeds because it generates the types first |

Other CI observations:

* **The repository has no git remote** (`git remote -v` is empty), so this workflow has never run anywhere. Everything above is a local replay (M-02).
* Triggers `push` and `pull_request` with no filter: PR branches run twice. No `concurrency` group, no `permissions: contents: read` block (default token rights), actions pinned by major tag, not by SHA.
* Missing gates that PHASE10_PLAN promised: real-Postgres test job, Playwright smoke, `npm audit` / `pip-audit`. The OpenAPI snapshot check is inside pytest (good).
* Python and Node versions match the dev machine (3.13, Node 22). `@types/node` is ^20 while CI/dev run Node 22 (cosmetic).
* The job does not depend on local state besides the `tsc` ordering above (no `.env`, no venv path, no secrets).

### 8.2 Tracked files (`git ls-files`: 406)

| Check | Result |
|---|---|
| Env files tracked | none; only `apps/api/.env.example`. `apps/api/.env` and `apps/web/.env.local` are ignored (`git check-ignore` confirmed) and never appeared in any commit (checked all history for file names matching env/pem/secret/credential) |
| Generated files tracked | none (`tsconfig.tsbuildinfo`, `next-env.d.ts`, `.next`, `__pycache__` ignored) |
| `.claude/` | only `launch.json` tracked (dev servers; Windows `venv/Scripts/uvicorn.exe` path, harmless). `.claude/settings.local.json` is **not** ignored: if one is created it can be committed by accident (L-10) |
| Large files | largest: `package-lock.json` 359 KB, `PROJECT_DOCUMENTARY.md` 150 KB, `openapi_snapshot.json` 69 KB, `favicon.ico` 26 KB. No binaries of concern |
| Unused assets | `apps/web/public/{file,globe,next,vercel,window}.svg` (create-next-app leftovers) are referenced nowhere |
| Empty / dead package | `apps/api/app/interviews/voice/__init__.py` (voice is browser-side; the package is a leftover). The other empty files are normal `__init__.py` |
| Stray scratch/debug files, scratch routes | none tracked (`git ls-files` grep for scratch/tmp/debug/bak/preview: none; the only `app/api` routes are the two resume handlers) |
| `apps/web/.gitignore` | contains `.env*`, which would also ignore a future `apps/web/.env.example` (needs a `!.env.example` line) |
| Root files | **no root README.md**, no root `package.json`, no `.gitattributes`, no `.editorconfig`, no `docs/DEPLOY.md` / `LAUNCH_CHECKLIST.md`. `apps/web/README.md` is boilerplate; `AGENTS.md`/`CLAUDE.md` in `apps/web` are Next-generated agent notes |
| Line endings | `core.autocrlf=true` and no `.gitattributes`: the index holds LF for all text files, 33 working-tree files are CRLF and `apps/api/tests/integration/test_auth_flow.py` has **mixed** endings. Cause of the "LF will be replaced by CRLF" warnings. Add `.gitattributes` with `* text=auto eol=lf` (L-11) |
| Duplicate content | `docs/IMPLEMENTATION.md` section 6 vs `PRODUCT.md` partially overlap (consequence of staleness, section 6) |

---

## 9. Secrets and configuration

### 9.1 Secret scan (values never printed)

| Scan | Scope | Result |
|---|---|---|
| JWT-looking tokens (`eyJ...`) | all tracked files at HEAD and every commit (`git log --all -G`) | none |
| `sk-...`, `sk-ant-...`, `gsk_...`, `sbp_...`, `sb_secret_...`, `BEGIN ... PRIVATE KEY` | HEAD + all history | none |
| `AIza...` | one hit in commit `ea43292` and at HEAD: `scripts/llm_smoke.py` line 161, a 40-character string containing the marker `INVALID`, used as a deliberately bad key for a negative test; the other matches are test fixtures like `AIza-sec...`. Not a real key. | benign |
| `service_role` / `secret =` assignments | docs, tests | names only, no values |
| Env files in history | all commits | only `.env.example` |

Result: **no secret in the repository or in its history.** (Rotation of keys that were pasted into chat sessions is still on the launch checklist: the documentary records that credentials were shared with the assistant; that is outside git and not verifiable here.)

### 9.2 Environment variable inventory

Backend (`apps/api/app/core/config.py`):

| Variable | Required | Secret | In `.env.example` | Used | Notes |
|---|---|---|---|---|---|
| SUPABASE_URL | yes (boot check) | no | yes | yes | |
| SUPABASE_SERVICE_ROLE_KEY | yes (boot check) | **yes** | yes | yes | bypasses RLS |
| SUPABASE_JWT_SECRET | no | **yes** | yes | yes (HS256 fallback; blank = HS256 refused) | |
| KEY_ENCRYPTION_SECRET | yes (valid Fernet, comma list allowed) | **yes** | yes | yes | |
| STORAGE_ENDPOINT_URL / STORAGE_ACCESS_KEY_ID / STORAGE_SECRET_ACCESS_KEY / STORAGE_BUCKET_NAME | required only when `ENVIRONMENT=production` | access key id and secret | yes | yes | Supabase S3 keys are project-wide, not bucket-scoped |
| STORAGE_REGION | no (default us-east-1) | no | yes | yes | |
| ENVIRONMENT | no, **defaults to `development`** | no | yes | yes | forgetting it in production leaves OpenAPI docs open and skips the production checks (L-12) |
| CORS_ORIGINS | no, default localhost | no | yes | yes | |
| GEMINI_API_KEY, GROQ_API_KEY, ANTHROPIC_API_KEY | scripts only | **yes** | no (docstrings only) | owner-run scripts | not read by the server |

Web (`apps/web`):

| Variable | Public? | Used in | Documented | Notes |
|---|---|---|---|---|
| NEXT_PUBLIC_SUPABASE_URL | public by design | `lib/supabase/*`, `proxy.ts` | **no example file** | |
| NEXT_PUBLIC_SUPABASE_ANON_KEY | public by design (RLS is the guard) | same | no example file | |
| NEXT_PUBLIC_API_URL | public by design | `lib/api-client/fastapi.ts`, resume route | no example file | |
| STORAGE_ENDPOINT_URL, STORAGE_REGION, STORAGE_ACCESS_KEY_ID, STORAGE_SECRET_ACCESS_KEY, STORAGE_BUCKET_NAME | **server-only** (`lib/storage.ts` imports `server-only`) | resume route handlers | no example file | secret S3 key lives in Vercel env at launch |

No `NEXT_PUBLIC_` variable carries a secret. Variables used but undocumented: all web variables (no `apps/web/.env.example`; the CI workflow is the only place listing the three public ones) and the script keys. Documented but unused: none.

---

## 10. Dependencies and supply chain

### 10.1 npm (`apps/web`)

`npm audit`: 9 findings (2 low, 2 moderate, 5 high), **none critical**. `npm audit --omit=dev`: 2 low.

| Finding | Scope | Assessment |
|---|---|---|
| dompurify 3.4.13-3.4.15 (GHSA-p98j-92pf-mc4p, DOM XSS through an `IN_PLACE` + afterSanitize hook edge case) via monaco-editor | production (transitive of `@monaco-editor/react`) | low; Monaco uses it internally for its own widgets, no app-supplied HTML. `npm audit fix` (non-breaking) |
| eslint-config-next chain: braces, micromatch, fast-glob, @next/eslint-plugin-next (high) | dev only | lint-time ReDoS class; never shipped. npm proposes a nonsensical downgrade to 14.2.35: ignore and wait for upstream |
| vitest / @vitest/mocker (moderate) | dev only | fix is the major vitest 5 |

`npm outdated`: next 16.3.7 -> 16.3.8 (patch, take it), eslint-config-next 16.3.8, @aws-sdk/client-s3 3.1146.0, framer-motion 13.4.6 -> 13.5.1 (14.0.0 major), react 19.2.8 -> 19.3.0, vitest 3.2.7 -> 5.0.3 (major), eslint 9 -> 10, typescript 5.9.3 -> 7.0.2 (major, skip for now), @types/node 20 -> 26 (use 22). **Unused declared dependencies**: `zustand`, `zod`, `@react-three/drei` (no imports found in `app`, `components`, `lib`).

### 10.2 Python (`apps/api`)

All versions are pinned to December 2024 releases. `pip-audit` (run on the clean venv, 49 advisory rows incl. duplicates and the dev-only `pip`/`pytest`):

| Package | Pinned | Advisories | Relevance |
|---|---|---|---|
| cryptography | 43.0.3 | 6 distinct (fixes up to 49.0.0) | Fernet encryption of provider keys; upgrade is routine |
| starlette (via fastapi 0.115.6) | 0.41.3 | 7 distinct (fixes up to 1.3.1) | the HTTP layer of the whole API; upgrade fastapi |
| pdfminer.six (via pdfplumber 0.11.4) | 20231228 | 2 (fix 20251107 / 20251230) | **parses user-uploaded PDFs**: highest relevance; exploitability not assessed here (needs verification against the advisory text) |
| python-jose | 3.3.0 | 3 (fix 3.4.0) incl. the known algorithm-confusion and JWE-bomb CVEs, plus `ecdsa` (transitive, no fix) | mitigated in code (`algorithms` pinned, no JWE accepted) but flagged by every scanner; 3.5.0 exists or move to PyJWT |
| pip, pytest | dev tooling | | not shipped |

`pip list --outdated` also shows: fastapi 0.115.6 (0.142.2), pydantic 2.10.3, supabase 2.10.0 (2.32.0; the pinned supabase pulls the deprecated `gotrue` package, which warns at import), anthropic 0.40.0 (1.11.0), groq 0.13.1 (1.7.0), httpx 0.27.2 (0.28.1), boto3 1.35.75, uvicorn 0.32.1. The majors of anthropic/groq/supabase are API-breaking; the adapters have recorded-fixture-style unit tests but no live check, so upgrade with the owner-run smoke script ready. The developer venv still contains packages no longer in `requirements.txt` (APScheduler, google-generativeai and its gRPC stack): harmless, but the dev venv is not the CI venv.

EOL notes: Node 22 LTS fine; Python 3.13 fine; Next 16 / React 19 current; ESLint 9.39.5 flagged unsupported by npm (move to 10 when eslint-config-next supports it).

---

## 11. Operations readiness

### 11.1 Single-process assumptions (all verified in code)

Per-process state: per-key limiter (`llm/limiter.py`), user throttle (`core/throttle.py`, documented "in-process, single-instance"), key cooldowns (`llm/keystate.py`), query-embedding cache and ATS requirements cache, job semaphore (`core/jobs.py`), per-interview turn locks, background-task registry, report sweeper (6 h timer). The Dockerfile/start command therefore **must run exactly one uvicorn worker** (no `--workers`, no gunicorn with several workers).

Boot recovery: `_recover_jobs()` marks **every** queued/running job failed at startup and aborts half-made interviews / frees code submissions. Correct for one process; if a platform ever briefly runs two instances (rolling deploy overlap), the new instance would fail the old one's live jobs (M-04, needs verification of Render's free-plan deploy behaviour).

### 11.2 Health, readiness, logging, validation

* `/health` is dependency-free; `/ready` checks the database with one cheap read and answers 503 without detail. `/health/authenticated` exists. Good.
* Startup `validate_config()` refuses to boot with missing Supabase URL/service key/encryption key, a bad Fernet key, and (production) missing storage settings, empty or localhost CORS. Docs/OpenAPI are disabled when `ENVIRONMENT=production`.
* JSON logs with request ids (`X-Request-ID` exposed), no tokens or prompts. No metrics, no error tracker, no alerting (only logs).
* Graceful shutdown waits up to 8 s for background summaries/digests; in-flight jobs are not drained and will be failed by the next boot's recovery (acceptable).

### 11.3 Retention and growth

| Data | Cleanup today | Growth risk |
|---|---|---|
| interview_reports | purged at read, at boot, on list, every 6 h (needs the API awake; read-time refusal is authoritative) | none |
| ats_scores | pruned to the last 10 per resume by `record_ats_score` | bounded: 10 x 3 resumes x user |
| jobs | **never deleted** | one row per setup/review/report (small rows, but unbounded; `result` may hold the interviewer's reply). L-13 |
| notifications | never deleted (client can only mark read) | tiny |
| llm_usage | one row per user/provider/kind/day, never pruned | tiny |
| chat_messages / conversations | user deletes conversations | unbounded text; **client can insert directly** (H-01) |
| interview_transcripts, interviews | user deletes interviews; no auto-expiry | ~60 turns per interview; fine |
| Storage objects | deleted with the resume; **orphaned when a user is deleted** | 500 KB x 3 per user |

### 11.4 Free-tier limits and what happens at the limit

| Limit (published free-tier figures; confirm in the dashboards) | Consequence |
|---|---|
| Supabase DB 500 MB (live: 12 MB) | past the limit the project goes read-only: every write (chat, interviews, key saves) fails with a database error. Direct client inserts (H-01) make it reachable by one abusive account |
| Supabase Storage 1 GB (live: 143 KB) | 3 resumes x 500 KB x user = 1.5 MB worst case, about 650 fully-loaded users; uploads then fail with a 502 from the route |
| Supabase free projects pause after about a week of inactivity | the API's `/ready` goes 503 and every page errors until the owner resumes the project in the dashboard; not mentioned in any doc (M-06) |
| `max_connections=60` | not a concern: the API uses the HTTP (PostgREST) client |
| Render free: sleeps after 15 min, about 1 min cold start, 750 h/month | handled by the waking-server banner and polled jobs; a request that arrives during boot of a *cold* instance may lose its in-flight job (recovery marks it failed) |
| Vercel Hobby: 4.5 MB body cap, 300 s functions | upload cap is 500 KB; resume POST waits for processing inside the function (fine within 300 s) |
| Gemini free quota per Google project | handled (Pacific day, failover, 429 mapping) and measured per user in "Used today"; the interview round trip count is small by design |

### 11.5 Deployment files still to write (none exist) and what they must contain

* **Dockerfile (apps/api)**: `python:3.13-slim`, non-root user, `pip install --no-cache-dir -r requirements.txt` (not the dev file), copy `app/` (+ `scripts/` if the owner-run tools should be available), `CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}` with **one worker**, no `--reload`; `.dockerignore` excluding `venv/`, `tests/`, `.env*`, `__pycache__`, `.pytest_cache`.
* **render.yaml**: one `web` service, `plan: free`, `runtime: docker`, `healthCheckPath: /health` (not `/ready`, so database blips do not restart it), `autoDeploy` as the owner chooses, and `envVars` for every backend variable in 9.2 with `sync: false` for each secret and `ENVIRONMENT=production`, `CORS_ORIGINS` set to the Vercel URL (no localhost).
* **docs/DEPLOY.md**: Supabase (apply 0001-0029 in numeric order; create the private `resumes` bucket with 500 KB and PDF/DOCX limits; create the S3 access key; Google provider; Site URL and redirect URLs for the Vercel domain; disable email signup and enable leaked-password protection), Render, Vercel (root `apps/web`, the eight variables in 9.2), keep-warm option, first sign-in becomes Owner (so the owner must sign in first), load starter questions.
* **scripts/check_deploy.py**: read-only: GET `/health`, GET `/ready` (expect 200), GET `/docs` and `/openapi.json` (expect 404), CORS preflight `OPTIONS /keys` with `Origin: <vercel url>` (expect allow-origin and allow-credentials), and a negative preflight from `http://evil.example` (expect no allow-origin).
* **docs/LAUNCH_CHECKLIST.md** (proposed content):
  1. Create a GitHub remote and push (none exists yet); confirm CI is green (fix H-02 first).
  2. Rotate every secret shared during development: Supabase service-role key and JWT secret (legacy), S3 access key, Gemini key of the owner; re-enter in Render/Vercel; `KEY_ENCRYPTION_SECRET` rotate via `scripts/rotate_keys.py`.
  3. Apply the new hardening migration (H-01, M-01, L-02, L-03) and re-run advisors.
  4. Delete the demo sign-up route and link; in Supabase Auth disable email sign-ups and confirm-email settings accordingly; enable leaked-password protection.
  5. Production env: `ENVIRONMENT=production`, `CORS_ORIGINS` exact Vercel origin, docs 404, one worker.
  6. Owner-run scripts in this order with the owner's key: `load_starter_questions --apply`, `llm_smoke --record` (fills `tests/fixtures/gemini`), `rag_eval_live`, `judge_eval_live`, `report_eval_live`; record results in FACTS.md and set the ATS calibration constants.
  7. Manual walk-through on the deployed site: sign-in, key, chat, upload, ATS (3 runs, history), interview text + voice (Chrome/Edge) + coding submit, report (print/text, delete), team page, question bank, rename/delete flows, second account.
  8. Dependency upgrades (section 10), then re-run the whole suite.
  9. Check Supabase dashboards (DB size, storage, auth settings, project not paused).

---

## 12. Findings (ranked)

Every finding below was confirmed by reading the file or querying the live catalog unless it is in 12.5. No CRITICAL finding: nothing found lets one tenant read or alter another tenant's data, and no secret is in git. Severity reflects the stated goal (owner testing now, public free-tier launch next).

### 12.1 CRITICAL

None.

### 12.2 HIGH

**H-01. Signed-in users can write directly to `chat_messages`, `conversations`, `resume_chunks` (and `notifications`, `profiles`) with no size or row limits**
* Where: live grants (`information_schema.role_table_grants`): `authenticated` holds INSERT/UPDATE/DELETE on these tables; RLS only restricts rows to the caller's own. Introduced by Supabase default privileges; 0019 and 0028 tightened `provider_keys`, `interviews`, `interview_transcripts`, `resumes` but not these.
* What is wrong: the web app needs none of those writes except `DELETE` on `conversations` and `UPDATE is_read` on `notifications`, `INSERT` on `profiles`. Every other write goes through the API (which has caps and throttles).
* Failure scenario: sign-in is open to any Google account. Anyone signs up, takes their JWT and the public anon key from the browser, and POSTs multi-megabyte `content` rows to `/rest/v1/chat_messages` in a loop (or a million rows into `resume_chunks`). The free database reaches 500 MB and Supabase makes it read-only: sign-ins, chats, interviews and key saves fail for everybody until it is cleaned up. A user can also forge assistant messages into their own chat history (harmless to others).
* Minimal fix (one migration, no app change): `revoke insert, update on chat_messages, conversations, resume_chunks from authenticated;` keep `delete` on `conversations`; `revoke insert, delete on notifications from authenticated` and keep `update (is_read)`: `revoke update on notifications from authenticated; grant update (is_read) on notifications to authenticated;` `revoke update on profiles from authenticated; grant update (full_name) on profiles to authenticated;` `revoke all on llm_usage from authenticated; grant select on llm_usage to authenticated;` and for `roles`, `admin_permissions` revoke all write privileges (the team page uses the API). Optionally add a CHECK `char_length(full_name) <= 120`.

**H-02. The CI web job fails on a clean checkout**
* Where: `.github/workflows/ci.yml` (web job, step `npx tsc --noEmit` precedes `npx next build`), `apps/web/app/layout.tsx:24` uses the global `LayoutProps<"/">`.
* What is wrong: `LayoutProps` comes from Next's generated types (`.next/types`, `next-env.d.ts`), both gitignored. Reproduced on a fresh clone: `app/layout.tsx(24,50): error TS2304: Cannot find name 'LayoutProps'.` (the only error). Locally the type check passes because the generated files exist.
* Scenario: the first push to GitHub shows a red build on the web job at its first real step, hiding every other result.
* Minimal fix: in the workflow run `npx next typegen` (verify the exact command in `node_modules/next/dist/docs`) before `tsc`, or run `npx next build` first and drop the separate `tsc`.

### 12.3 MEDIUM

**M-01. Two foreign keys have no ON DELETE action and block deleting a user**
* Where: `admin_permissions.granted_by -> profiles(id)` and `question_bank.created_by -> profiles(id)` (live constraint list: no `ON DELETE`).
* Scenario: the owner removes an admin (Supabase dashboard > Authentication > delete user) who created question-bank entries, or removes the Owner's test account that granted permissions: deleting `auth.users` cascades to `profiles`, which is refused with a foreign-key violation (23503), surfacing as "Database error deleting user". Account deletion (and any future "delete my account" feature, and GDPR-style erasure) is blocked.
* Fix: `alter table admin_permissions drop constraint admin_permissions_granted_by_fkey, add constraint ... foreign key (granted_by) references profiles(id) on delete set null;` same for `question_bank.created_by`.

**M-02. The repository has no git remote**
* Where: `git remote -v` is empty.
* Scenario: the whole project (74 commits, docs, migrations) exists only on one laptop; CI has never run; Render and Vercel cannot deploy from it.
* Fix: create a private GitHub repository and push; then fix H-02 and watch the first CI run.

**M-03. No verified fresh-install path for the database**
* Where: `apps/api/migrations/` vs live history (section 2.1): an applied migration without a file (`fix_remaining_rls_initplan`, folded into 0009 afterwards), applied names differ from file names, 0023/0024 were applied before 0020/0021, `0007` needs Supabase's `extensions` schema, and nothing replays the files on an empty database.
* Scenario: the owner creates a separate production Supabase project and applies 0001-0029 by hand; a statement that only works on the original project's history fails midway and leaves a half-built schema, or silently differs (for example a missing policy that lived in the lost migration).
* Fix: replay 0001-0029 once in numeric order on a throw-away Supabase project (or a Postgres with the Supabase roles shim) and diff the catalog against production with the queries used in this audit; rename files to match history or add a note; this is the "real-Postgres tests" item of PHASE10_PLAN.

**M-04. Boot recovery fails every active job**
* Where: `app/main.py::_recover_jobs` -> `jobs.fail_all_active`.
* Scenario (needs verification of the platform's deploy behaviour): during a deploy the old and new instances overlap; the new one fails the old one's running interview setup, code review or report, aborts the interview being set up and frees the candidate's submission while the old instance is still working on it, which then writes results onto a failed job.
* Fix: restrict recovery to jobs whose `heartbeat_at` is older than `STALE_AFTER_SECONDS` (the column and the constant already exist) instead of all active jobs.

**M-05. Gemini model is a moving alias**
* Where: `app/llm/models.py` `_GEMINI = "gemini-flash-lite-latest"`; PILLARS_PLAN M2.8 and FACTS.md promised pinned IDs and a `last_verified` date.
* Scenario: Google repoints `-latest` to a model with different thinking defaults, quota, JSON behaviour or price; interview turns and JSON-mode extraction change behaviour with no deploy; the adapter's thinking config (`thinkingLevel: minimal`) may be rejected.
* Fix: pin an explicit model id once `llm_smoke --record` has run against it; keep the alias only as a fallback entry; record `last_verified`.

**M-06. Free-tier pause and monitoring are undocumented and unmonitored**
* Where: no doc mentions that a free Supabase project pauses after inactivity; there is no uptime monitor, error tracker or alert.
* Scenario: the owner demos the app after a quiet week; `/ready` is 503, every page errors, and the cause is not obvious.
* Fix: add it to DEPLOY.md and the launch checklist; add a free uptime monitor on `/ready` (also keeps Render warm); verify the pause rule in the dashboard.

**M-07. The question bank is empty on the live database**
* Where: live `question_bank` has 0 rows (and 0 embeddings); `scripts/load_starter_questions.py` was written for the owner to run but has not been.
* Scenario: the owner starts a Coding, Web Dev or SDE interview: there is no problem to ask and nothing for the code editor to submit against, so the flagship coding round cannot be tested.
* Fix: owner runs `python -m scripts.load_starter_questions --apply` (3 problems, 1 embedding request).

**M-08. Email/password sign-up path is still reachable**
* Where: `app/(auth)/sign-up/DemoSignUpView.tsx` and its link on the sign-in page; Supabase Auth email-signup and confirmation settings are not visible from SQL (needs verification); advisor `auth_leaked_password_protection` is on WARN.
* Scenario: after launch anyone creates accounts with throw-away emails, skipping the "Google only" principle, multiplying the abuse surface of H-01.
* Fix: delete the route, the link and the page; disable email sign-ups (keep Google) in Supabase Auth; enable leaked-password protection.

**M-09. The documentation set contradicts the product**
* Where: section 6. PRODUCT.md (the "single A-Z reference") is dated 2026-10-02 and describes R2, Judge0, stub Team/Reports pages, "no ATS history", 504 tests; the documentary's "read this first" snapshot is from the morning of the first live run.
* Scenario: the owner (or a new maintainer or agent) follows the docs: configures R2 instead of Supabase Storage, believes Team/Reports are stubs, or applies the wrong migration list.
* Fix: apply the corrections in 6.1/6.2 (about two hours of editing), add the missing sections of 6.4, and put a banner on IMPLEMENTATION.md and PILLARS_PLAN.md.

**M-10. Known vulnerabilities in pinned Python packages**
* Where: `apps/api/requirements.txt` (pip-audit, section 10.2): cryptography 43.0.3, starlette 0.41.3 (via fastapi 0.115.6), pdfminer.six 20231228 (via pdfplumber 0.11.4; processes user-uploaded PDFs), python-jose 3.3.0 (+ `ecdsa`).
* Scenario: a public API running year-old HTTP and PDF-parsing libraries with published advisories; the PDF parser handles attacker-supplied files.
* Fix: upgrade fastapi/starlette, cryptography, pdfplumber/pdfminer.six and python-jose (3.5.0) or switch to PyJWT in one pass with the suite and `llm_smoke` ready; assess the two pdfminer advisories first (needs verification).

### 12.4 LOW

| ID | Location | What is wrong | Failure scenario | Minimal fix |
|---|---|---|---|---|
| L-01 | policies `question_bank_select_all`, `question_bank_write/update/delete_permission` | The table's client privileges were revoked (0020), leaving four dead policies; `select_all` would expose reference solutions to every signed-in user if a later migration re-granted SELECT | someone grants SELECT to build an admin feature and leaks `solution_code` | `drop policy question_bank_select_all`; keep the write policies only if the table is ever exposed |
| L-02 | `admin_permissions_admin_key_unique` + `admin_permissions_admin_permission_uq`; `idx_admin_permissions_admin_id`, `idx_interview_transcripts_interview_id`, `idx_interview_reports_interview_id` | Duplicate unique constraint (0019 and 0021 both added it) and three prefix-redundant indexes (advisor WARN duplicate_index) | wasted writes and storage, lint noise | drop `admin_permissions_admin_key_unique` (constraint) and the three redundant indexes |
| L-03 | `code_submissions.question_id`, `.user_id` | FK columns without index (advisor) | slow cascade/SET NULL when a user or question is deleted, once the table has rows | `create index on code_submissions (question_id); create index on code_submissions (user_id);` |
| L-04 | `roles` policies + `team/service.py` | DB allows the Owner (through the public API) to demote themselves; nothing ensures an owner remains; the first-owner trigger fires only on profile insert | Owner demotes self by a direct PATCH to `/rest/v1/roles`; nobody can manage the team any more | revoke client write on `roles`/`admin_permissions` (also H-01 fix) so only the API (which refuses owner changes) writes |
| L-05 | table-level grants and `pg_default_acl` | `authenticated` also holds TRUNCATE, REFERENCES, TRIGGER on all tables; default privileges still grant anon/authenticated on every future table and function | a future migration that forgets its `revoke` exposes a new table; TRUNCATE is not reachable through PostgREST but is through any direct SQL role | `alter default privileges in schema public revoke all on tables from anon, authenticated;` same for functions; revoke truncate/references/trigger |
| L-06 | `provider_keys.user_id`, `resumes.user_id`, `interviews.user_id`, `conversations.user_id`, `notifications.user_id`, `admin_permissions.admin_id`, `interview_transcripts.interview_id`, `chat_messages.conversation_id`, `resume_chunks.resume_id` | Owner columns are nullable | NULL-owner rows are invisible but could accumulate from a bug in a service-role insert | `set not null` (tables are small or empty) |
| L-07 | `db/*` RPC wrappers | A P0002 raised inside `append_*`, `record_ats_score`, `replace_resume_chunks` is not mapped; the API returns the generic 500 (how PostgREST surfaces P0002 needs verification) | a row deleted between the ownership check and the RPC gives a 500 instead of 404 | catch `APIError` with that code and raise `AppError(404, "not_found")` |
| L-08 | `app/api/resumes/route.ts` GET | selects full `parsed_text` of every resume only to learn whether it is processed | up to 3 resumes x 500 KB of text on every list/refresh | select a boolean via a view or `content_hash` instead |
| L-09 | user deletion path | Storage objects `resumes/<uid>/...` are not removed when a user is deleted | orphaned files count against the 1 GB quota | delete the prefix in the account-deletion procedure (script or future endpoint) |
| L-10 | `.gitignore` | `.claude/settings.local.json` not ignored | local permission settings committed by accident | add `.claude/settings.local.json` |
| L-11 | repo root | no `.gitattributes`; `autocrlf=true`; 33 CRLF files in the working tree and one file (`tests/integration/test_auth_flow.py`) with mixed endings | CRLF warnings and noisy diffs across machines/CI | add `* text=auto eol=lf` and normalise |
| L-12 | `core/config.py` | `ENVIRONMENT` defaults to `development` | forgetting it in Render leaves OpenAPI docs and localhost CORS on and skips the production validation | require the variable explicitly (fail if missing) or default to production |
| L-13 | `jobs`, `notifications` tables | no retention | slow, unbounded growth | delete jobs older than 30 days (in the report sweeper) |
| L-14 | `db/team.py` | user list capped at 200 (`per_page=200`, `limit(200)`); `replace_permissions` is delete then insert, not atomic | Owner cannot see user 201+; a failure between the two calls leaves an admin with no permissions | paginate; do it in one RPC |
| L-15 | `apps/web/package.json`, `apps/web/public`, `apps/api/app/interviews/voice/` | unused deps `zustand`, `zod`, `@react-three/drei`; unused create-next-app svgs; empty `voice` package | install size, confusion | remove |
| L-16 | web env | no `apps/web/.env.example`; `apps/web/.gitignore` has `.env*` which would ignore one | a new setup has to guess 8 variables | add the file and `!.env.example` |
| L-17 | `db/questions.list_questions`, `question_bank.test_cases` | the old answer-key column `test_cases` is still selected and returned to admins and is no longer used | confusing, an unused answer key kept | drop the column when convenient |

### 12.5 Needs verification (not confirmed)

1. Supabase Auth settings: whether email sign-ups/confirmation are enabled; whether the legacy HS256 JWT secret is still active (it should be rotated at launch).
2. Whether Render's free plan overlaps instances during deploys (M-04).
3. Exploitability of the pdfminer.six and starlette advisories for this API's usage (M-10).
4. How PostgREST reports SQLSTATE P0002 to supabase-py (L-07).
5. The exact Next 16 command for generating route types (`next typegen`) for H-02.
6. Whether the Supabase free-tier figures quoted in 11.4 still apply to this project (check the dashboard).
7. That migrations 0001-0029 replay cleanly in numeric order (M-03): reasoned from reading, not executed.
8. Live behaviour of everything in 7.1 marked BUILT.

---

## 13. Prioritised upgrades (effort: S under half a day, M one to two days, L several days)

### Before the owner's own testing (today)
1. (S) Owner: run `load_starter_questions --apply` so coding interviews have problems (M-07).
2. (S) One hardening migration, with the owner's go-ahead, covering H-01, M-01, L-01, L-02, L-03, L-04, L-05, L-06; then re-run `get_advisors` (security first).
3. (S) Fix the CI `tsc` ordering (H-02) and create the GitHub remote (M-02).
4. (S) Add a short top-of-file banner on IMPLEMENTATION.md, PILLARS_PLAN.md and the documentary snapshot so nobody follows stale instructions (M-09, first stage).

### Before launch
5. (M) Rewrite PRODUCT.md from section 6 and fill 6.4 (M-09).
6. (M) Upgrade Python dependencies and re-run the suite plus `llm_smoke` (M-10); `npm audit fix` and Next 16.3.8.
7. (S) Run the owner-run scripts (`llm_smoke --record`, `rag_eval_live`, `judge_eval_live`, `report_eval_live`), pin the Gemini model, set ATS constants (M-05).
8. (S) Delete demo sign-up; disable email sign-up; enable leaked-password protection (M-08).
9. (M) Dockerfile, `.dockerignore`, `render.yaml`, `DEPLOY.md`, `check_deploy.py`, `LAUNCH_CHECKLIST.md` (11.5).
10. (M) Fresh-database replay of migrations and a catalog diff; ideally the real-Postgres CI job (M-03).
11. (S) Job recovery by heartbeat (M-04); make `ENVIRONMENT` explicit (L-12).
12. (S) Uptime monitor on `/ready`, documented pause behaviour (M-06).
13. (S) `.gitattributes`, `.gitignore` fixes, web `.env.example`, root README (L-10, L-11, L-16).
14. (S) Rotate every secret that was shared during development.

### After launch (correctness, then UX)
15. (S) Map P0002 to 404; atomic permission replacement; pagination of the team list (L-07, L-14).
16. (S) Job and notification retention in the sweeper (L-13).
17. (M) Account deletion procedure that also removes storage objects (L-09).
18. (M) Playwright smoke test with an accessibility scan; screen-reader pass on the interview room.
19. (M) Add `llm_usage.feature/model` if per-feature cost visibility is wanted; error tracking and basic metrics.
20. (L) Move to pgvector HNSW only if the question bank exceeds ~10k rows; async Supabase client only if thread-pool saturation shows up.
21. (L) Optional premium voice (Gemini Live/TTS) behind the existing `VoiceIO` seam; practice mode; anti-cheat.
