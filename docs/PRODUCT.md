# CyntraAI: Complete Product Document (A to Z)

> Snapshot date: **2026-10-04** | Repo: `C:\Study\Project4-Cyntra AI\Cyntra_AI` | Branch `main` | HEAD `0f719d9` (75 commits)
> This is the single "everything about the product" reference. Companion files: `docs/README.md` (index of every document and whether it is current), `docs/PROJECT_DOCUMENTARY.md` (chronological build journal; start with its current STATE SNAPSHOT), `docs/DEPLOY.md` and `docs/LAUNCH_CHECKLIST.md` (owner runbooks), `docs/FACTS.md` (external facts and what is still unverified), `docs/audit/*.md` (final audit reports).

> Working-tree note (2026-10-04): this document describes the committed state at HEAD `0f719d9` plus the final audit. An **uncommitted** batch of fixes was in the working tree while this was written (security headers and error/not-found pages in the web app, the demo sign-up gate `lib/demo-signup.ts`, job recovery by stale heartbeat `app/jobs/recovery.py`, newer Python pins, CI `next typegen`, `apps/web/.env.example`, a draft migration `0030_final_hardening.sql`). Where a statement below says the audit found a problem, check `git log` and `git status` to see whether it has since been fixed; nothing in that batch was verified by the documentation pass.

**Status legend (used throughout):**

| Label | Meaning |
|---|---|
| LIVE | Built and observed working against the real stack (real Supabase, real Gemini key) |
| BUILT | Built and covered by automated tests with mocks/fakes; **never run against live data** (the live database holds 0 rows for it) |
| DROPPED | Deliberately not built (decision recorded) |
| DEFERRED | Postponed on purpose |

---

## 1. What CyntraAI is

A **single-tenant AI platform** with three services under one account system, run on a **BYOK (Bring Your Own Key)** model: users supply their own LLM API keys, so the platform pays nothing for LLM usage and the infrastructure targets **$0/month** (Vercel Hobby + Render free + Supabase free).

| Service | One-line description | Status |
|---|---|---|
| **AI Chatbot** | Chat with any provider you have a valid key for (Gemini / Claude / Groq), streamed | LIVE with Gemini (2 conversations, 9 messages on the live database); Claude and Groq adapters BUILT |
| **AI Interviewing Agent** | Timed 1-hour mock interviews in 8 types, personalised from a resume and a job description. Text, browser voice, and a coding round (reviewed against a reference solution, nothing executed), then an on-demand 7-day report | BUILT (0 interviews, 0 reports, 0 code submissions on the live database) |
| **AI Resume ATS Score** | Scores a resume against a JD like a real ATS (keyword + semantic + formatting + written feedback); keeps the last 10 checks per resume | Scoring LIVE (the owner ran a check on 2026-10-03, before history existed); history BUILT (0 `ats_scores` rows) |

**Roles:** *Owner* (the first user ever; full control) | *Admin* (permissions individually granted by the Owner; today the only permission is `manage_question_bank`) | *Application User*.

---

## 2. Feature catalog

### 2.1 Accounts, auth and roles
| Feature | Status |
|---|---|
| Google sign-in (Supabase Auth, OAuth) | LIVE |
| Account-setup step (Gmail shown read-only + set a password used as an *alternate login*) | LIVE |
| Profile + role created automatically; **first user becomes Owner** (DB trigger `private.handle_new_profile`, race-safe) | LIVE |
| Route guards (signed in, account setup, onboarding, dashboard), role/permission helpers (`requireRole`, `requirePermission`) | LIVE |
| Backend JWT verification (ES256 via JWKS, HS256 fallback, `exp` required, blank secret refuses HS256) | LIVE |
| **Team management** (`/settings/team`, Owner only): list users, change a role, grant/revoke permissions. API `GET /team/users`, `PATCH /team/users/{id}/role`, `PUT /team/users/{id}/permissions` | BUILT (0 `admin_permissions` rows live) |
| Temporary demo email/password sign-up page (`app/(auth)/sign-up`) | exists and is linked from the sign-in page at HEAD; **must be removed or disabled before launch** (see `docs/LAUNCH_CHECKLIST.md`). An uncommitted change (`apps/web/lib/demo-signup.ts`) turns it off in production builds unless `NEXT_PUBLIC_ENABLE_DEMO_SIGNUP=true` is set at build time; unverified |

### 2.2 BYOK key system
| Feature | Status |
|---|---|
| Providers: Gemini, Claude, Groq; **primary + backup slot** each | Gemini LIVE; Claude and Groq BUILT |
| Gemini key **mandatory** (only embeddings provider); Claude/Groq optional | LIVE |
| Keys encrypted at rest (Fernet, `MultiFernet` for rotation); never returned to the client; the table's `encrypted_key` column is not readable by browsers | LIVE |
| Server-side validation before storing (Gemini: list-models, no quota; Claude/Groq: one tiny call); bad keys are never stored | Gemini LIVE |
| Guided onboarding with per-provider instructions; Settings > API Keys management; **key delete with confirmation** (warns when deleting a Gemini primary) | LIVE (onboarding); delete BUILT |
| Automatic silent failover primary to backup on rate limit, then a notification; **notifications bell** in the app shell (polls every 60 s, mark as read) | BUILT (0 notification rows live) |
| "Used today" usage line (requests / tokens per provider, Pacific quota day for Gemini) | LIVE (2 `llm_usage` rows) |

### 2.3 AI Chatbot
| Feature | Status |
|---|---|
| Conversations list, thread, streamed replies, provider selector (only providers with valid keys), copy | LIVE (Gemini) |
| History window: last 10 messages, further fitted to a 3,000-token budget (`chat/service.py`) | LIVE |
| Friendly errors (no key, quota, overloaded, blocked reply) | LIVE |
| **Rename a conversation** (`PATCH /chat/conversations/{id}`; list rows and thread header) and **delete** (direct from the browser under RLS; messages cascade) | BUILT |

### 2.4 Resumes and RAG (shared by ATS and Interviews)
| Feature | Status |
|---|---|
| Upload PDF/DOCX (**<= 500 KB**: web route, API `_MAX_FILE_BYTES` and the bucket limit 512,000 bytes; extension + file-signature check) to the private **Supabase Storage** bucket `resumes` through the S3 API | LIVE (1 resume, 1 storage object) |
| **At most 3 resumes per user**: UI pre-check plus a database trigger (`resumes_limit_before_insert`, migration 0028/0029); the upload route maps the trigger's `resume_limit` error to a 409 | BUILT (trigger proven in a rolled-back transaction on 2026-10-04) |
| **Rename a resume** (`resumes.display_name`, 1-80 chars; `PATCH /api/resumes/{id}` under the user's own session and column grant) | BUILT |
| Parse (pdfplumber / python-docx), section-aware chunking (v2), one batched Gemini embedding (768-d, `gemini-embedding-001`), atomic chunk replace | LIVE (1 resume, 7 chunks) |
| One-time resume digest (~300 tokens) reused by interviews (non-fatal if it fails) | BUILT |
| Retry processing; delete (cascades chunks and ATS history, nulls `interviews.resume_id`, then deletes the storage object) | LIVE (processing); delete BUILT |
| Question bank retrieval (cosine similarity, diversity-aware selection) | BUILT (question bank is empty live) |

### 2.5 ATS Resume Score
| Feature | Status |
|---|---|
| JD to structured requirements (LLM, JSON mode, cached in memory per user+JD for 1 h) | LIVE (owner run, 2026-10-03) |
| Keyword score (whole word, synonyms), semantic score (calibrated coverage over embeddings), formatting score (heuristics) combined into a 0-100 composite (40/40/20), **all sub-scores shown**, evidence per requirement | LIVE (owner run, 2026-10-03: "worked, score looked right"). The semantic window constants `LOW`/`HIGH` in `app/ats/semantic.py` are still placeholders until the owner runs `scripts/rag_eval_live.py` |
| Written actionable feedback (LLM; parsed into clean items by `lib/ats/feedback.ts`) | LIVE (owner run) |
| **History: the last 10 checks per resume are stored** in `ats_scores` (migration 0028, pruned atomically by `record_ats_score`); `GET /ats/history`, `GET|DELETE /ats/history/{id}`; "Previous checks" panel (list, open with a banner, delete) | BUILT |
| An empty requirements extraction returns 422 (never a fake high score) | BUILT |

### 2.6 Interviewing Agent
| Feature | Status |
|---|---|
| 8 interview types: **Coding, Behavioral, HR, ML/AI, Web Dev, SDE, System Design, Case Study**, each with its own phase list and time split (always 60 min total) | BUILT |
| Setup is a **polled background job** (`jobs`, kind `interview_setup`): pick a resume + paste a fresh JD; one embed + one structured call produces a brief and a personalised opening; progress text; **Cancel setup** (`POST /interviews/{id}/abort`) | BUILT |
| Orchestrator: phases advance by elapsed time; the interview is auto-completed after its time plus a 5-minute grace | BUILT |
| Token-lean turns: brief + phase goal + running summary + last turns, bounded prompt, capped reply; incremental running summary in the background | BUILT |
| Interview providers: **Gemini + Groq only** (Claude is excluded) | BUILT |
| Interview room UI (transcript, phase/timer, send answer, end interview) | BUILT |
| **Delete an interview** (`DELETE /interviews/{id}`; cascades transcript, code submissions, report) | BUILT |
| Question bank admin (Owner, or Admin with `manage_question_bank`): question, **reference solution + language**, tags, topic, difficulty; embedded on save; clearing topic/difficulty sends an explicit null. The legacy `test_cases` column still exists but is no longer entered and is unused. Reference solutions never reach candidates (client privileges on the table are revoked) | BUILT (0 rows live) |
| **Coding round** (only in Coding, Web Dev, SDE): Monaco editor beside the chat, any language, **one submit per problem**, a confirmation before submitting. The submit starts a `code_review` job: **one LLM call compares the candidate's logic with the question bank's reference solution; nothing is ever executed**. The verdict is hidden from the candidate; the interviewer sees a short summary and reacts. A failed review (provider outage) does not use up the submit | BUILT (0 `code_submissions` rows live); `scripts/judge_eval_live.py` not yet run |
| **Voice** (browser only): speech recognition in, speech synthesis out; live captions, silence endpointing with edit-before-send (default 2.5 s, 1.5-4 s adjustable), canned spoken nudges at about 20 s of silence (no LLM call), optional "allow interrupting"; typing always works. Needs Chrome/Edge for recognition (Firefox has none; Safari partial, unverified). Backend is unchanged (the text `/turns` endpoint) | BUILT, awaiting hands-on test. The audit found four voice bugs (turning voice on mid-interview does not read the pending question; the closing message can be cut off; a `speak()` race can let the mic hear the interviewer; a microphone error latches until reload): see `docs/audit/FRONTEND_AUDIT.md` M-3 to M-6 |
| **Post-interview report**: on demand (`POST /interviews/{id}/report`, throttled 3/min, needs a completed interview with at least 3 candidate answers). One LLM call; the overall score is computed in code; quotes are verified against the transcript; stored code verdicts included. Available for **exactly 7 days** (`expires_at` set by the database default, refused at read time with 410 once expired, purged at startup, on list and every 6 hours by an in-API sweep). Print-to-PDF, text/Markdown export, delete now | BUILT (0 `interview_reports` rows live); `scripts/report_eval_live.py` not yet run |
| Untimed practice mode | DEFERRED |
| Session recording/playback | DROPPED (declined) |
| Anti-cheat (tab-switch monitoring) | DEFERRED |

### 2.7 UI/UX
| Feature | Status |
|---|---|
| Light + dark themes with design tokens, icon theme toggle; "calm career coach" visual refresh (2026-10-04) | BUILT (agents checked sign-in/privacy in a preview browser; the owner's click-through of every logged-in page is pending) |
| Motion: route transitions, list/score animations; `prefers-reduced-motion` honoured by CSS, framer-motion and the 3D scene (one gap: JavaScript `scrollIntoView({behavior:"smooth"})` calls ignore it, audit M-10) | BUILT |
| 3D loading scene (three.js, lazy) used only on the interview-setup wait screen | BUILT |
| Skeletons, empty states, in-app `ConfirmDialog` and toasts (no browser `confirm`), retry states, skip link, labelled controls, "waking server" banner | BUILT. Screen-reader testing was not done |
| Dashboard shell with sidebar and mobile nav | BUILT |
| Privacy page (`/privacy`): what is stored, what leaves the app, how to delete; it has no contact email yet and does not mention the Monaco CDN (audit L-14) | BUILT |

---

## 3. Architecture and tech stack

```
Browser --- Next.js 16 (Vercel) ------------------> Supabase (Postgres 17 + pgvector + Auth + Storage)
   |          * auth/session (proxy.ts)               ^
   |          * resume upload/list/rename/delete      | service role (backend) / RLS + column grants (browser)
   |            route handlers ---> Supabase Storage (private bucket `resumes`, S3 API)
   `- Bearer JWT -> FastAPI (Render, ONE worker) -----'
                     * core: security (JWT, Fernet), config, db, storage, jobs, throttle
                     * llm: gateway -> limiter -> provider adapters (Gemini REST / Claude / Groq)
                     * keys, chat, rag, ats (+history), interviews (+question bank), coding, reports, team, jobs, usage
                     * no code execution, no WebSocket, no voice backend
```

| Layer | Choice |
|---|---|
| Frontend | Next.js 16.3.7 (TypeScript, App Router, Turbopack), React 19.2.8, Tailwind v4, next-themes, framer-motion, three / `@react-three/fiber` (lazy), `@monaco-editor/react` (Monaco itself loads from a CDN at runtime), `@supabase/ssr`, `@aws-sdk/client-s3` (server-only, resume upload) |
| Backend | Python 3.13 (code needs >= 3.11), FastAPI 0.115.6, pydantic 2.10, supabase-py 2.10 (sync client run in threads), boto3 (S3 API), cryptography (Fernet), pdfplumber, python-docx, httpx; Gemini via REST (no SDK), `anthropic`, `groq` SDKs |
| Data | Supabase Postgres 17.11 + pgvector 0.8.2 (768-d vectors, exact scan), RLS on every table |
| Storage | **Supabase Storage** (S3-compatible endpoint), private bucket `resumes`: 500 KB limit, PDF/DOCX only, no `storage.objects` policies (all access through the S3 key). Free tier 1 GB |
| Code execution | **None.** The Judge0 plan was withdrawn on 2026-10-03; the coding round is a logic review against a reference solution |
| Hosting (planned, not yet deployed) | Vercel Hobby (web) + Render free (API) + Supabase free. No Dockerfile or `render.yaml` exists yet; see `docs/DEPLOY.md` |
| Tests | Backend `pytest`: **605 passed + 1 skipped** (the skip is `test_recorded_fixtures`: no recorded Gemini fixtures exist). Frontend `vitest`: **158 passed in 24 files**. `tsc`, `eslint`, `next build` clean locally. CI (`.github/workflows/ci.yml`) has never run (no git remote); at HEAD its web job fails on a clean checkout because `tsc` runs before Next generates `LayoutProps` (audit H-02; an uncommitted `npx next typegen` step is in the working tree, unverified) |

### 3.1 Trust model
Next.js owns light CRUD that needs no LLM: authentication, resume upload/list/rename/delete, and a few direct reads/writes under the user's own session. FastAPI owns everything that touches an LLM, embeddings, jobs, code review, reports and team management. The browser calls FastAPI directly with the Supabase JWT; FastAPI verifies it independently and uses the **service role**, so ownership is enforced in code (every query is scoped by `user_id`; only `apps/api/app/db/*` touches Supabase, enforced by `tests/test_architecture.py`).

Database-level protection (verified against the live catalog on 2026-10-04):
- RLS is enabled on all 17 tables. `jobs`, `code_submissions`, `interview_reports`, `ats_scores` have **no policy and no client privilege** (backend only). `question_bank` has all client privileges revoked (reference solutions are unreachable from browsers).
- `authenticated` can read only the non-secret columns of `provider_keys`; `interviews` and `interview_transcripts` are read-only to browsers; `resumes` allows insert of `(id, user_id, file_key)` and update of `display_name` only; a CHECK forces `file_key` under `resumes/<own uid>/`.
- Known weakness (audit H-01): `authenticated` still holds table-level INSERT/UPDATE/DELETE, limited to own rows but not by size, on `chat_messages`, `conversations`, `resume_chunks`, `notifications`, `profiles`, `llm_usage`, `roles`, `admin_permissions`. A hardening migration draft exists (see `docs/PROJECT_DOCUMENTARY.md` current snapshot for its status); confirm with `list_migrations` before assuming it is applied.

### 3.2 Repository map
```
apps/web   app/(auth)  sign-in | account-setup | onboarding | sign-up (demo, temporary)
           app/(dashboard)  dashboard | chat(+[conversationId]) | interviews(+setup,+[interviewId]) | ats-score | resumes
                            reports(+[interviewId]) | settings/api-keys | settings/team | admin/question-bank
           app/privacy | app/api/resumes (+[id]) | app/auth/callback | proxy.ts
           lib/ (supabase clients, api-client, auth guards, storage, voice, resumes, team, ats, reports)
           components/ (ui, chat, settings, interview, ats, three)   test/ (vitest setup)
apps/api   app/core (config, security, jobs, throttle, errors, middleware, storage, background, pagination)
           app/db (the only Supabase layer)  keys  chat  rag(+parsing)  ats  interviews(+types, voice[empty leftover])
           coding  reports  team  jobs  llm(+prompts)  providers
           migrations/0001-0029   scripts/ (owner-run tools)   tests/ (unit, integration, rag_eval, judge_eval, report_eval, openapi_snapshot.json)
docs/      PRODUCT.md, README.md (index), PROJECT_DOCUMENTARY.md, IMPLEMENTATION.md, PILLARS_PLAN.md, PHASE7-10_PLAN.md,
           FACTS.md, FRONTEND_GAPS.md, UI_REFRESH.md, DEPLOY.md, LAUNCH_CHECKLIST.md, audit/ (3 reports)
```

### 3.3 HTTP API inventory
All FastAPI routes (39 operations; the authoritative list is `apps/api/tests/openapi_snapshot.json`, pinned by a test). Every route except `/health` and `/ready` requires a Supabase JWT. Errors use one envelope with a stable `code` and a request id.

| Area | Routes | Notes |
|---|---|---|
| Health | `GET /health` (no dependencies), `GET /ready` (checks the database; 503 without detail), `GET /health/authenticated` | Use `/health` for platform health checks, `/ready` for humans/monitors |
| Keys | `POST /keys` (10/min), `GET /keys`, `DELETE /keys/{id}` | Validates before storing |
| Chat | `POST /chat/conversations`, `GET /chat/conversations`, `PATCH /chat/conversations/{id}` (rename), `GET /chat/conversations/{id}/messages`, `POST /chat/conversations/{id}/messages` (streams text) | Unthrottled; bounded by the per-key limiter |
| RAG | `POST /rag/resumes/{id}/process` (6/min) | Download, parse, chunk, embed, store |
| ATS | `POST /ats/score` (6/min), `GET /ats/history`, `GET /ats/history/{id}`, `DELETE /ats/history/{id}` | Last 10 per resume |
| Interviews | `POST /interviews` (4/min, returns 202 + job), `GET /interviews`, `GET /interviews/{id}`, `GET /interviews/{id}/transcript`, `POST /interviews/{id}/turns`, `POST /interviews/{id}/complete`, `POST /interviews/{id}/abort`, `DELETE /interviews/{id}` | |
| Question bank | `POST /interviews/question-bank`, `GET /interviews/question-bank`, `PATCH /interviews/question-bank/{id}`, `DELETE /interviews/question-bank/{id}` | Owner or Admin with `manage_question_bank` |
| Coding | `GET /interviews/{id}/problem` (question text only), `POST /interviews/{id}/submissions` (6/min, 202 + job) | One submit per problem; max 8,000 characters of code, language up to 30 characters |
| Jobs | `GET /jobs/{id}` | Owner-scoped polling of setup, code review and report jobs |
| Reports | `POST /interviews/{id}/report` (3/min, 202; `ready: true` if one exists), `GET /reports`, `GET /reports/{interview_id}` (410 once expired), `DELETE /reports/{interview_id}` | 7-day expiry |
| Team | `GET /team/users`, `PATCH /team/users/{id}/role`, `PUT /team/users/{id}/permissions` | Owner only; the user list is capped at 200 |
| Usage | `GET /usage` | Today's per-provider usage |

Next.js route handlers: `GET|POST /api/resumes`, `PATCH|DELETE /api/resumes/{id}`, `GET /auth/callback`. Throttles are per user, in-process, fixed 60-second windows.

### 3.4 Data model (live: 17 tables, RLS on all, migrations 0001-0029 applied)
| Table | Purpose |
|---|---|
| `profiles`, `roles`, `admin_permissions` | Identity, Owner/Admin/User role, per-admin permissions |
| `provider_keys` | Encrypted BYOK keys (unique per user, provider, slot) |
| `notifications` | Failover / key-problem notices shown by the bell |
| `resumes` (+`digest`, `content_hash`, `embed_version`, `display_name`) | Resume metadata and parsed text; max 3 per user (trigger) |
| `resume_chunks` | Section-labelled chunks with `vector(768)`, generated `tsvector` (GIN) |
| `conversations`, `chat_messages` | Chat |
| `interviews` (+`brief`, `running_summary`, `summarized_through_turn`, `selected_question_ids`, `provider`) | Interview state; unique `(interview_id, turn_index)` on transcripts |
| `interview_transcripts` | Turns |
| `question_bank` (+`difficulty`, `topic`, `solution_code`, `solution_language`, `embed_version`) | Questions with reference solutions; backend only |
| `interview_reports` | Report JSON, `overall_score`, `expires_at` default now()+7 days, one per interview; backend only |
| `llm_usage` | Per user/provider/kind/day requests and tokens incl. `thought_tokens` |
| `jobs` | Background jobs (queued/running/succeeded/failed, progress, heartbeat); one active job per user+kind |
| `code_submissions` | One non-failed submission per (interview, question); verdict hidden; backend only |
| `ats_scores` | Last 10 ATS results per resume; backend only |

Functions: 7 `SECURITY DEFINER` (`private.is_owner`, `private.has_admin_permission`, `private.handle_new_profile`, `append_interview_turns`, `append_chat_exchange`, `record_ats_score`, `enforce_resume_limit`; all pin `search_path`; none is callable through the REST API) plus invoker functions `record_llm_usage`, `replace_resume_chunks`, `match_resume_chunks_multi`, `match_question_bank_v2` (service role only). Triggers: `on_profile_created`, `resumes_limit_before_insert`. A migration `0030_final_hardening.sql` exists as an uncommitted draft in the working tree at the time of writing (client-write revocations, duplicate-constraint cleanup, FK fixes, extra indexes); it is **not** part of the 0001-0029 set described here.

---

## 4. How things work, step by step

**Sign-in to dashboard.** Google OAuth, callback, no `profiles` row? account-setup (set password, create profile; trigger assigns role, first user = Owner), no valid primary Gemini key? onboarding, dashboard.

**Saving a key.** Browser `POST /keys`, backend **validates first** (Gemini lists models; others a tiny call), only a valid key is encrypted and upserted; an invalid, rate-limited or unreachable provider gives a clear error and nothing is stored.

**Every LLM call (the gateway).** The feature builds messages and `LLMOptions(task, caps, temperature, json_mode)`, then `gateway.complete/stream/embed`: per-key limiter (queues up to 20 s), provider adapter with timeouts, retry on overload, failover to the backup key on rate limit (+ notification), usage recorded. Errors map to 412 no key, 429 quota, 503 overloaded, 504 timeout, 400 key rejected, 422 reply blocked. Nothing is retried or failed over once streamed output has started. Untrusted text (JD, resume, answers, code) is wrapped in random-delimiter data blocks and replies pass a leak filter.

**Chat.** Window of the last 10 messages, fitted to 3,000 tokens; streamed reply (the first chunk is pre-fetched so early errors are real JSON errors); both messages are saved atomically (`append_chat_exchange`) when the reply completes.

**Resume upload.** Browser, Next route (validate extension, signature, 500 KB, 3-resume limit), Supabase Storage via S3, `resumes` row (the database trigger is the real limit), then FastAPI process: download, parse, section-aware chunks (at most 60), **one** batched embed, digest (non-fatal), atomic chunk replace, `parsed_text` set last (a failure leaves it retryable).

**ATS score.** Extract requirements (JSON mode, cached 1 h), one batched embed of the terms, one multi-term retrieval RPC, keyword + semantic + formatting, composite, feedback call, result saved (last 10 per resume).

**Interview.** *Start:* validate resume and key, create the interview in `setting_up`, create a `interview_setup` job (202). The job embeds the JD, picks questions from the bank (Coding and Web Dev 2, SDE 1, others 0), makes one structured call returning `{brief, opening}` (fallback if malformed), then sets `in_progress` and `ends_at = now + 60 min`. The page polls `GET /jobs/{id}`. *Each turn:* phase from elapsed time, system prompt (type, phase goal, brief, current question only in problem phases) + summary + last turns, one call, both turns saved atomically (`append_interview_turns`), incremental summary in the background. *Time up:* more than 60 + 5 minutes completes the interview and answers 409. *Code submit:* checks ownership, in-progress, a problem phase active, size, not already submitted; a `code_review` job makes one structured call (question, reference solution, candidate code as untrusted data); the verdict is stored, the interviewer's message is written to the transcript atomically. *Abort/delete:* abort frees a half-made setup; delete removes the interview and everything under it. *Report:* a `report_generate` job builds an evidence pack (no LLM), makes one structured call, verifies quotes, computes the score, stores it with a 7-day expiry.

**Boot recovery.** At startup the API marks every queued or running job failed (jobs run inside the process), aborts half-made interviews and frees code submissions whose review was interrupted; it also deletes expired reports. This is correct for one worker; see Known limitations. (An uncommitted change restricts recovery to jobs with a stale heartbeat and adds a periodic sweep, `app/jobs/recovery.py`; unverified.)

| Interview type | Phases (minutes) | Coding round | Bank questions |
|---|---|---|---|
| Coding | intro 5 / problem_1 25 / problem_2 25 / wrap_up 5 | yes | 2 |
| Web Dev | intro 5 / problem_1 25 / problem_2 25 / wrap_up 5 | yes | 2 |
| SDE | intro 5 / coding 20 / system_design 20 / behavioral 10 / wrap_up 5 | yes | 1 |
| Behavioral | warm_up 5 / questions 45 / wrap_up 10 | no | 0 |
| HR | warm_up 5 / questions 40 / wrap_up 15 | no | 0 |
| ML/AI | intro 5 / concepts 25 / case_study 25 / wrap_up 5 | no | 0 |
| System Design | intro 5 / design_discussion 45 / wrap_up 10 | no | 0 |
| Case Study | intro 5 / case_presentation 10 / discussion 35 / wrap_up 10 | no | 0 |

Coding-round behaviour in one place: the editor appears only while a problem phase is active in Coding, Web Dev and SDE; the candidate may discuss the problem in the chat; **Submit** (once per problem, after a confirmation) sends code and language; the reviewer judges **by logic against the reference solution** (a different valid approach is accepted); **nothing is run**, so runtime errors and performance traps can be missed; the verdict is never shown during the interview and the interviewer guides with follow-ups instead of announcing correct/incorrect; the full verdict appears only in the post-interview report. With a thin question bank a second problem can repeat the first and cannot be submitted (audit BE-H1), and SDE has no starter question: load more questions before relying on this.

---

## 5. Complete decisions log

**Product and scope**
1. Fresh rebuild (an earlier project was erased); single-tenant; roles Owner/Admin/User with per-admin granular permissions.
2. Three services; build order Chat, RAG, ATS, Interviews so the provider/failover plumbing is proven on the simplest service first.
3. Interview types: the original six plus **System Design** and **Case Study**. Fixed **1 hour**, per-type phases. Timed mode only; **practice mode deferred**; **recording declined**; **anti-cheat deferred**.
4. Interview = Gemini + Groq only (Claude excluded; the original reason was no native audio, which is no longer relevant because voice is browser-side, but the restriction is unchanged).
5. ATS: **history reversed on 2026-10-04**: the last 10 checks per resume are stored (earlier decision was "no history"); sub-scores always shown; same resume pipeline.
6. Reports: available for **exactly 7 days**, then purged; generated on demand, not automatically.
7. Question bank: Owner (+ Admins with `manage_question_bank`) only. The original "test cases are an answer key" decision was replaced by **reference solutions**, which must never reach candidates.
8. **No code execution** (Judge0 plan withdrawn 2026-10-03): the coding round is a one-submit-per-problem logic review.
9. **Voice is browser speech APIs** (recognition + synthesis), not Gemini Live: free, no backend change, no 15-minute session cap, at the cost of system-voice quality and Chrome/Edge-only recognition.

**BYOK and auth**
10. Gemini mandatory (embeddings are Gemini-only); Claude/Groq optional; primary + backup keys; Fernet encryption; server-side validation; silent failover then notify.
11. **Google-only** sign-in; the password is just an alternate login. A temporary demo email sign-up exists and must be removed or disabled at launch.

**Infrastructure**
12. Everything free: Vercel + Render + Supabase ($0/month). **Storage is Supabase Storage (S3 API)**: Cloudflare R2 was planned first, then replaced on 2026-10-03. **Redis dropped.** Judge0 withdrawn.
13. Monorepo `apps/web` + `apps/api`. Two-layer backend: Next route handlers for light CRUD, FastAPI for AI.
14. pgvector inside Postgres (no separate vector DB); embeddings `gemini-embedding-001` at 768 dims; exact scan (HNSW only if the question bank passes about 10k rows).
15. **One API worker**: limiter, throttles, caches, job semaphore, turn locks and the report sweeper are per process.
16. Resume cap 500 KB and 3 resumes per user (free-tier storage and Vercel's 4.5 MB body cap); presigned direct upload dropped; async Supabase client deferred.

**LLM architecture (approved 2026-10-02)**
17. All model traffic through **one gateway**; prompts short, structured, capped; JSON mode over prose; never resend distilled data (JD to brief, turns to summary, resume to digest).
18. Default Gemini model is the **lite `-latest` alias** (`gemini-flash-lite-latest`), about 0.9 s to first token versus 6-7 s for the thinking flash model (measured on 2026-10-02) and a far larger free quota. The pillars plan promised pinned IDs; that was **not done** (see Known limitations).
19. Embeddings batched. Quotas are **per Google project**, reset at midnight **Pacific**; a backup key only helps if it is from a different project.

**Working agreements**
20. Discuss, finalise, written plan, approval, implement; every executed step is logged in the documentary.
21. **No live LLM-provider calls by the assistant** (free-tier quotas are tiny): verification uses mocks, `tsc`/`eslint`/`build`, and the owner tries live paths and runs the owner-run scripts.
22. Frontend files: `page.tsx` is a thin re-export of a properly named `XView.tsx`.
23. Migrations are applied only with the owner's explicit go-ahead; secrets are never typed, logged or documented.
24. Commit trailer: `Co-Authored-By: Claude Sonnet 5.5`.

---

## 6. What has been built (chronological)

| Date | Step | Outcome |
|---|---|---|
| 09-27 | **Planning** | Scope, stack, schema, 10-phase plan written and approved |
| 09-30 | **Phase 1** foundation | Monorepo, Supabase project + migrations, Google auth flow, account setup, role trigger, guards, design system, dashboard shell, JWT verification |
| 10-01 | **Phase 2** BYOK | Adapters (Gemini/Claude/Groq), Fernet encryption, validation, failover, onboarding + settings UI |
| 10-01 | Demo sign-up; naming cleanup; theme toggle | Dev convenience page (temporary); `page.tsx` + named views |
| 10-01 | **Phases 3-6** | Chat; RAG foundation; ATS; text interview core |
| 10-02 | **First live run** | Real Google sign-in, onboarding, encrypted key, streamed chat verified; found/fixed an ES256-vs-HS256 token bug, `.env` path bug, retired Gemini models, 503 handling, slow model |
| 10-02 | LLM architecture steps 1-6; self-audit; 3-agent audit of phases 1-6 | Gateway, batching, interview/ATS diet, usage; 132 integration tests; migration 0019 |
| 10-02 | **Pillars plan** and milestones M0-M3 | Safety net, platform core (error envelope, request ids, db layer), LLM hardening (REST Gemini, limiter, structured output, injection standard), RAG v2 (migration 0020) |
| 10-03 | **Storage switch** R2 to Supabase Storage; 500 KB cap | Verified live (upload + processing) |
| 10-03 | **M4** jobs and atomicity | Migrations 0021 (atomic turns), 0022 (jobs), 0025 (atomic chat) |
| 10-03 | **Phases 7-9** (redesigned) | Coding review (0026), browser voice (frontend only), reports (0027) |
| 10-03 | **Phase 10** hardening and polish | Cleanup, `/ready`, key rotation, OpenAPI snapshot test, privacy page; deployment set aside |
| 10-04 | Project audit; **UI refresh**; **frontend rounds 2-3** | In-app dialogs/toasts, resume-delete fix, 158 frontend tests |
| 10-04 | **Pending backend features** | Migrations 0028 (resume rename, 3-resume limit, column grants, ATS history) and 0029 (revoke trigger function) |
| 10-04 | **Final whole-project audit** (3 agents) | `docs/audit/*.md`: 0 critical, 2 high (H-01 unbounded client writes, H-02 CI red on clean checkout) |

Migrations 0001-0029 are applied live (apply order differed slightly from numeric order and one applied migration, `fix_remaining_rls_initplan`, has no file; see the documentary).

---

## 7. Current state at a glance

### 7.1 Verified live vs mock-tested only

| Area | Verification |
|---|---|
| Google sign-in, account setup, Owner role, route guards, JWT verification | **Live** |
| BYOK Gemini key (encrypted, validated, "Used today") | **Live** |
| Chat (streaming, Gemini) | **Live** |
| Resume upload to Supabase Storage + processing (parse, chunk, embed, store) | **Live** (1 resume, 7 chunks) |
| ATS check (requirements, scores, feedback, results page) | **Live** (owner ran one on 2026-10-03; recorded in the documentary). It predates ATS history, so no `ats_scores` row exists and history is untested live |
| Claude and Groq adapters, failover, notifications bell | Mock-tested only |
| 3-resume trigger, resume rename, column grants, file-key CHECK | Proven in a rolled-back live transaction on 2026-10-04 (not through the UI) |
| Interview setup, turns, summaries, abort/delete, question selection | Mock-tested only |
| Question bank admin and the starter questions (bank is empty) | Mock-tested only |
| Coding round and code review | Mock-tested only |
| Voice (recognition, synthesis, nudges) | Unit-tested helpers only; needs a hands-on test in Chrome/Edge |
| Reports (generation, expiry, export, delete) | Mock-tested only |
| Team management | Mock-tested only |
| Chat rename, ATS history panel, delete flows, all 2026-10-04 UI work | Component-tested only; the owner's click-through is pending |
| Deployment (Render, Vercel, Supabase redirect URLs) | Not done |


### 7.2 Credentials and configuration
Supabase keys and the encryption secret are in `apps/api/.env` (gitignored); the Owner's Gemini key is stored encrypted in the database; Supabase S3 storage keys are configured; **no Groq or Claude key has been added**. Secrets that were shared in chat sessions during development must be rotated at launch (see `docs/LAUNCH_CHECKLIST.md`). No secret is in git or its history (scanned 2026-10-04).

### 7.3 Known limitations
- **Free-tier limits.** Supabase free: 500 MB database, 1 GB storage, projects pause after about a week of inactivity (published figures, not verified for this project); a paused project makes `/ready` return 503 and every page error until it is resumed in the dashboard. Render free: sleeps after 15 min idle, cold start about 1 min, 750 instance-hours/month, ephemeral disk. Vercel Hobby: 4.5 MB body cap, 300 s function limit. Gemini free quotas are per Google project, so a backup key from the same project does not help.
- **Single-process design.** The API must run exactly one worker. Throttles, per-key limiter, key cooldowns, caches, the job semaphore (6 concurrent jobs), turn locks and the report sweeper are in-process. At HEAD boot recovery marks every active job failed, so an overlapping second instance during a deploy would kill the other's live jobs (audit M-04; unverified how Render's free plan behaves; an uncommitted change makes recovery heartbeat-based).
- **Unverified model assumptions.** `gemini-flash-lite-latest` is a moving alias (not pinned). Whether `thinkingConfig.thinkingLevel: "minimal"` is accepted is unverified (the adapter drops it automatically if rejected). Claude (`claude-sonnet-5-5`) and Groq (`llama-3.1-8b-instant`, `llama-3.3-70b-versatile`) IDs were checked against provider docs on 2026-10-02 but never exercised with a key. Real Gemini 429/503 bodies were never recorded, so quota-type parsing is unproven. The ATS semantic `LOW`/`HIGH` constants are placeholders (the semantic score is 40% of the composite). Judge accuracy and report fairness are unmeasured until the owner-run scripts are run.
- **No code execution.** Runtime errors, performance traps and off-by-one slips can be missed by the reviewer; one submit per problem means a mistake cannot be corrected.
- **Voice** depends on the browser: Chrome/Edge recognition sends audio to Google; Firefox has no recognition; Safari is partial (unverified). Four known voice bugs are listed in the frontend audit.
- **Other.** Monaco loads from a third-party CDN at runtime (no offline fallback; not mentioned on the privacy page). At HEAD no HTTP security headers are configured in `next.config.ts` (audit M-1); an uncommitted change adds a conservative set (frame-ancestors, nosniff, referrer policy, microphone permission, no script/style/connect CSP), unverified. At HEAD the Python dependencies are pinned to December 2024 releases with published advisories (audit M-10); an uncommitted change raises several pins (fastapi, cryptography, pdfplumber, python-jose), not yet verified against the suite by this pass. `jobs` and `notifications` are never pruned. The question bank is empty until the owner loads the starter questions. The Team list is capped at 200 users. Resume-delete, user-delete (two foreign keys block deleting a user who granted permissions or created questions) and Storage orphaning on user deletion are documented in the audit (M-01, L-09).

---

## 8. What remains

The product build is complete; what is left is verification, hardening and deployment. Tracked in `docs/LAUNCH_CHECKLIST.md` and `docs/audit/*.md`.

| # | Item | Who | Notes |
|---|---|---|---|
| 1 | **Owner-run quality scripts**, in this order: `python -m scripts.load_starter_questions --apply` (3 problems, 1 embedding request), `llm_smoke --record` (about 10 requests; fills `tests/fixtures/gemini/` and records real error bodies and thinking facts), `rag_eval_live` (8 requests; set `LOW`/`HIGH` in `app/ats/semantic.py`), `judge_eval_live` (12 requests), `report_eval_live` (4 requests) | Owner (the assistant never runs them) | Record results in `docs/FACTS.md` |
| 2 | **Live click-through** of every feature on the owner's machine (list in `docs/LAUNCH_CHECKLIST.md`), including voice in Chrome/Edge | Owner | only sign-in/roles, BYOK Gemini, chat, resume upload + processing and one ATS check have run on live data (the final audit counted 4 of 22 feature rows live; it did not count the owner's 2026-10-03 ATS run) |
| 3 | **Deployment files and deploy**: `Dockerfile`, `.dockerignore`, `render.yaml` (one worker), `scripts/check_deploy.py`; then Render, Vercel, Supabase redirect URLs per `docs/DEPLOY.md` | Lead builds files; owner clicks | Not yet written |
| 4 | **Launch checklist** (`docs/LAUNCH_CHECKLIST.md`): rotate shared secrets, remove/disable the demo sign-up, enable leaked-password protection, set production env, privacy contact, backups, uptime monitor on `/ready` | Owner | |
| 5 | Hardening migration (client write privileges H-01, FK `ON DELETE SET NULL` M-01, duplicate constraint/indexes, missing FK indexes) | Needs the owner's go-ahead per migration | Draft `0030_final_hardening.sql` exists in the working tree |
| 6 | Create a git remote, fix the CI `tsc` ordering (H-02), watch the first CI run | Owner / lead | |
| 7 | Optional: real-Postgres CI tests (RPCs, constraints, grants), Playwright smoke + accessibility scan | Owner decision | Not built |
| 8 | Deferred optimisations: HNSW at about 10k questions, async Supabase client, cached decrypted key per request, fire-and-forget usage RPC, `pg_cron` purge, practice mode, anti-cheat, optional premium voice behind the `VoiceIO` seam | Later | |
| 9 | Dependency upgrades (fastapi/starlette, cryptography, pdfplumber/pdfminer.six, python-jose or PyJWT; Next 16.3.8; `npm audit fix`) with the suite and `llm_smoke` ready | Before launch | |

---

## 9. External facts (see `docs/FACTS.md` for sources, dates and what is unverified)

Render free: spins down after 15 min idle, about 1 min cold start, 750 instance-hours/month, ephemeral disk. Vercel: 4.5 MB request/response body cap; Hobby function max duration 300 s. Supabase free: 500 MB database, 1 GB storage, pauses after about a week of inactivity (published figures). Gemini: daily quotas reset at midnight Pacific and are per project; `gemini-embedding-001` needs manual normalisation below 3072 dimensions and takes at most 2,048 input tokens; lite models think by default (thought tokens billed separately). Claude IDs checked 2026-10-02: `claude-sonnet-5-5`, `claude-opus-5-5`, `claude-fable-5-1`, `claude-haiku-4-5-20251001` (Haiku 4.5 retirement not sooner than 2026-10-15). Groq production IDs: `llama-3.1-8b-instant`, `llama-3.3-70b-versatile`. The Judge0 and Gemini Live facts gathered earlier are kept in FACTS.md as history only.

---

## 10. How to run and verify

```bash
# API (from apps/api; venv at apps/api/venv)
source venv/Scripts/activate && python -m pytest -q     # 605 passed, 1 skipped
# Web (from apps/web)
npx tsc --noEmit && npx eslint . && npm test && npx next build   # npm test = vitest, 158 tests
```
Dev servers are defined in `.claude/launch.json` (`web` on :3000; `api` on :8000 launched from the repo root with `--app-dir apps/api`; the API has no auto-reload, restart it after backend edits). Environment files: `apps/api/.env` and `apps/web/.env.local` (never committed; values never recorded in docs). Note: `npx tsc --noEmit` passes locally only because `.next/` and `next-env.d.ts` exist; on a clean checkout it fails until Next has generated its route types (audit H-02).

### 10.1 Environment variables

Backend (`apps/api/.env`, template `apps/api/.env.example`):

| Variable | Required | Secret | Notes |
|---|---|---|---|
| `SUPABASE_URL` | yes | no | |
| `SUPABASE_SERVICE_ROLE_KEY` | yes | **yes** | Bypasses RLS |
| `SUPABASE_JWT_SECRET` | no | **yes** | HS256 fallback; blank means HS256 tokens are refused |
| `KEY_ENCRYPTION_SECRET` | yes | **yes** | One valid Fernet key, or several comma-separated (first encrypts, all decrypt) |
| `STORAGE_ENDPOINT_URL`, `STORAGE_ACCESS_KEY_ID`, `STORAGE_SECRET_ACCESS_KEY`, `STORAGE_BUCKET_NAME` | required when `ENVIRONMENT=production` | access key id and secret | Supabase Storage S3 connection |
| `STORAGE_REGION` | no (default `us-east-1`) | no | |
| `ENVIRONMENT` | no, **defaults to `development`** | no | `production` disables `/docs`, `/redoc`, `/openapi.json` and enforces the production checks; forgetting it leaves docs open |
| `CORS_ORIGINS` | no (default `http://localhost:3000`) | no | Comma-separated exact origins; production refuses to boot if it is empty or contains `localhost` |

Owner-run scripts additionally read `GEMINI_API_KEY`, `GROQ_API_KEY`, `ANTHROPIC_API_KEY` from the shell (never from the database; documented only in the script docstrings).

Web (`apps/web/.env.local`; template `apps/web/.env.example`, which exists only as an uncommitted file at the time of writing):

| Variable | Public | Notes |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` | yes by design (RLS is the guard) | |
| `NEXT_PUBLIC_API_URL` | yes | The API base URL, no trailing slash |
| `NEXT_PUBLIC_ENABLE_DEMO_SIGNUP` | yes | Optional, build-time. Only read by the uncommitted demo sign-up gate; leave unset in production |
| `STORAGE_ENDPOINT_URL`, `STORAGE_REGION`, `STORAGE_ACCESS_KEY_ID`, `STORAGE_SECRET_ACCESS_KEY`, `STORAGE_BUCKET_NAME` | **server-only** (`lib/storage.ts` imports `server-only`) | Used by the resume route handlers |
