# CyntraAI — End-to-End Implementation Plan (Detailed)

## 1. Context

CyntraAI is a from-scratch AI platform offering three services — an AI Chatbot, an AI Interviewing Agent, and an AI Resume ATS Score checker — unified under a **BYOK (Bring Your Own Key)** model, so the platform never bears LLM usage costs. This document is the single source of truth for architecture, folder structure, data model, and a granular step-by-step build order. **No implementation begins until this plan is explicitly approved.**

---

## 2. Tech Stack (final)

| Layer | Choice | Notes |
|---|---|---|
| Frontend | Next.js (TypeScript, App Router) | hosted on Vercel (free tier) |
| Backend — light CRUD | Next.js Route Handlers / Server Actions | auth-adjacent, settings, roles, metadata |
| Backend — AI engine | Python 3.11 + FastAPI | hosted on Render (free tier) |
| Database / Auth | Supabase Postgres + pgvector + Auth | free tier |
| File storage | Cloudflare R2 (S3-compatible) | free — 10GB, zero egress, resumes & reports |
| Cache | None (deferred) | Postgres/in-memory used where needed |
| Code execution | Judge0 (hosted free API via RapidAPI) | sandboxed test-case execution |
| Repo | Single monorepo | `apps/web` + `apps/api` |

Key libraries (indicative, confirmed at Phase 1 kickoff):
- FastAPI, `uvicorn`, `pydantic`, `supabase-py`, `boto3` (R2 is S3-compatible), `cryptography` (Fernet, for key encryption), `google-generativeai` (Gemini), `anthropic` (Claude), `groq` (Groq SDK), `pdfplumber` + `python-docx` (resume/JD parsing), `apscheduler` (report cleanup job), `websockets` (voice streaming), `pytest`, `httpx` (test client).
- Frontend: `@supabase/ssr`, `@monaco-editor/react`, `zustand` or React context for interview session state, `zod` for form/schema validation, Playwright for e2e tests.
- Frontend UI/UX: `next-themes` (light/dark theme switching), `framer-motion` (page/element transitions), `three` + `@react-three/fiber` + `@react-three/drei` (3D visuals for loading/setup screens), `tailwindcss` design tokens for both themes.

**Authentication**: Google OAuth only (via Supabase Auth's Google provider) — no email/password sign-up. See Section 7 for the detailed flow.

LLM usage costs are borne by users via BYOK; platform infra runs at **$0/month**.

---

## 3. Architecture Overview

```
apps/web (Next.js)                    apps/api (FastAPI)
├─ UI, auth, dashboards                ├─ LLM provider adapters (Gemini/Claude/Groq)
├─ Light CRUD via Route Handlers       ├─ Key encryption/validation/failover
│  (settings, roles, resume            ├─ RAG pipeline (parsing, chunking,
│   metadata, question bank CRUD)      │   embeddings, pgvector retrieval)
├─ WebSocket client (voice)  <-------->├─ Interview orchestration (phases,
                                       │   timers, voice streaming, summarization)
                                       ├─ ATS scoring pipeline
                                       └─ Judge0 client (code execution)
                        both  -------> Supabase (Postgres + pgvector, Auth)
                        both  -------> Cloudflare R2 (resumes, reports)
```

**Principle**: Next.js owns simple, role-gated data CRUD. FastAPI owns anything touching an LLM, embeddings/RAG, or real-time voice. Communication is an internal REST API plus a direct browser → FastAPI WebSocket for voice streaming.

**Auth trust model**: Supabase issues the JWT on login. Next.js validates it for its own Route Handlers via `@supabase/ssr`. For calls to FastAPI, Next.js forwards the Supabase JWT in an `Authorization: Bearer <token>` header; FastAPI verifies it against Supabase's JWT secret/JWKS on every request — FastAPI never trusts Next.js blindly, it independently validates the user's identity and role on each call.

---

## 4. Reference Folder Structure

```
cyntra-ai/
├─ apps/
│  ├─ web/
│  │  ├─ app/
│  │  │  ├─ (auth)/
│  │  │  │  ├─ sign-in/page.tsx           # "Continue with Google" only
│  │  │  │  ├─ account-setup/page.tsx     # first-time: uneditable Gmail + set password
│  │  │  │  └─ onboarding/page.tsx        # mandatory Gemini key step
│  │  │  ├─ (dashboard)/
│  │  │  │  ├─ layout.tsx
│  │  │  │  ├─ chat/
│  │  │  │  │  ├─ page.tsx
│  │  │  │  │  └─ [conversationId]/page.tsx
│  │  │  │  ├─ interviews/
│  │  │  │  │  ├─ page.tsx                # list / history
│  │  │  │  │  ├─ setup/page.tsx          # resume+JD upload, 5-min loading
│  │  │  │  │  └─ [interviewId]/page.tsx  # live room (voice + coding split)
│  │  │  │  ├─ ats-score/page.tsx
│  │  │  │  ├─ resumes/page.tsx
│  │  │  │  ├─ reports/page.tsx
│  │  │  │  ├─ settings/
│  │  │  │  │  ├─ api-keys/page.tsx
│  │  │  │  │  └─ team/page.tsx           # Owner-only
│  │  │  │  └─ admin/
│  │  │  │     └─ question-bank/page.tsx
│  │  │  └─ api/
│  │  │     ├─ resumes/route.ts
│  │  │     ├─ question-bank/route.ts
│  │  │     └─ team/route.ts
│  │  ├─ components/
│  │  │  ├─ ui/                           # Button, Card, Modal, Input, ThemeToggle, etc.
│  │  │  ├─ three/                        # reusable 3D scene components (react-three-fiber)
│  │  │  │  ├─ LoadingScene.tsx           # used on interview 5-min setup screen
│  │  │  │  └─ scenes/                    # individual .tsx scene definitions
│  │  │  ├─ chat/ChatWindow.tsx, MessageBubble.tsx
│  │  │  ├─ interview/
│  │  │  │  ├─ VoicePanel.tsx
│  │  │  │  ├─ TranscriptPanel.tsx
│  │  │  │  ├─ CodeEditorPanel.tsx
│  │  │  │  └─ PhaseTimer.tsx
│  │  │  └─ ats/ScoreBreakdown.tsx
│  │  ├─ lib/
│  │  │  ├─ supabase/client.ts, server.ts
│  │  │  ├─ auth/guards.ts                # role/permission checks
│  │  │  ├─ theme/ThemeProvider.tsx       # next-themes wrapper
│  │  │  └─ api-client/fastapi.ts         # typed fetch wrapper to FastAPI
│  │  └─ types/
│  │     ├─ interview.ts, ats.ts, roles.ts
│  │
│  └─ api/
│     ├─ app/
│     │  ├─ main.py
│     │  ├─ core/
│     │  │  ├─ config.py                  # env vars, settings
│     │  │  ├─ security.py                # Fernet encryption, JWT verification
│     │  │  └─ db.py                      # Supabase/Postgres session
│     │  ├─ providers/
│     │  │  ├─ base.py                    # ProviderAdapter ABC
│     │  │  ├─ gemini.py
│     │  │  ├─ claude.py
│     │  │  ├─ groq.py
│     │  │  └─ registry.py                # provider name -> adapter lookup
│     │  ├─ keys/
│     │  │  ├─ router.py                  # /keys endpoints
│     │  │  ├─ service.py                 # encrypt/store/validate/failover
│     │  │  └─ models.py
│     │  ├─ rag/
│     │  │  ├─ parsing/pdf.py, docx.py
│     │  │  ├─ chunking.py
│     │  │  ├─ embeddings.py
│     │  │  └─ retrieval.py
│     │  ├─ chat/
│     │  │  └─ router.py
│     │  ├─ interviews/
│     │  │  ├─ router.py
│     │  │  ├─ types/coding.py, behavioral.py, hr.py, ml_ai.py, webd.py, sde.py, system_design.py, case_study.py
│     │  │  ├─ orchestrator.py
│     │  │  ├─ voice/stt.py, tts.py, vad.py, ws_handler.py
│     │  │  ├─ summarizer.py
│     │  │  └─ question_bank.py
│     │  ├─ coding/judge0_client.py
│     │  ├─ ats/
│     │  │  ├─ router.py
│     │  │  ├─ requirements_extractor.py
│     │  │  ├─ scorer.py
│     │  │  └─ feedback.py
│     │  └─ reports/
│     │     ├─ router.py
│     │     └─ cleanup_job.py
│     ├─ migrations/                      # SQL migration files
│     └─ tests/
│        ├─ test_keys.py, test_chat.py, test_rag.py, test_ats.py, test_interviews.py
│
└─ packages/                              # shared types/config, added only if duplication appears
```

---

## 5. Data Model (Supabase Postgres + pgvector) — Detailed Schema

```sql
-- users mirror Supabase Auth via a profile table
create table profiles (
  id uuid primary key references auth.users(id),
  full_name text,
  created_at timestamptz default now()
);

create type role_type as enum ('owner', 'admin', 'user');

create table roles (
  user_id uuid primary key references profiles(id),
  role role_type not null default 'user'
);

create table admin_permissions (
  id uuid primary key default gen_random_uuid(),
  admin_id uuid references profiles(id),
  permission_key text not null,          -- e.g. 'manage_question_bank', 'manage_users'
  granted_by uuid references profiles(id),
  created_at timestamptz default now()
);

create type provider_name as enum ('gemini', 'claude', 'groq');
create type key_slot as enum ('primary', 'backup');

create table provider_keys (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references profiles(id),
  provider provider_name not null,
  slot key_slot not null,
  encrypted_key text not null,
  is_valid boolean default false,
  last_validated_at timestamptz,
  created_at timestamptz default now(),
  unique (user_id, provider, slot)
);

create table resumes (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references profiles(id),
  file_key text not null,                -- R2 object key (bucket is private, no public URL)
  parsed_text text,
  created_at timestamptz default now()
);

-- Added during Phase 4 implementation: a single embedding per resume can't
-- support real RAG retrieval (a JD requirement needs to match a *specific*
-- resume section, not the whole document). Supersedes resumes.embedding,
-- which existed in the original schema draft and was dropped.
create table resume_chunks (
  id uuid primary key default gen_random_uuid(),
  resume_id uuid references resumes(id) on delete cascade,
  chunk_index int not null,
  content text not null,
  embedding vector(768),                 -- gemini-embedding-001 @768, L2-normalized
  -- (M3 added: section text, embed_version text, content_tsv tsvector generated; resumes gained content_hash, embed_version;
  --  question_bank gained difficulty, topic, embed_version -- see migrations 0020 and 0024)
  created_at timestamptz default now()
);

-- pgvector cosine-similarity RPCs backing rag/retrieval.py, called via
-- Supabase's .rpc(). Plain functions (not SECURITY DEFINER) so RLS on the
-- underlying tables still applies if ever called directly by a client.
create or replace function match_resume_chunks(
  query_embedding vector(768), filter_resume_id uuid, match_count int default 5
) returns table (id uuid, content text, chunk_index int, similarity float)
language sql stable as $$ ... $$;

create or replace function match_question_bank(
  query_embedding vector(768), filter_type interview_type, match_count int default 5
) returns table (id uuid, question text, test_cases jsonb, tags text[], similarity float)
language sql stable as $$ ... $$;

create type interview_type as enum (
  'coding', 'behavioral', 'hr', 'ml_ai', 'webd', 'sde', 'system_design', 'case_study'
);
create type interview_status as enum ('setting_up', 'in_progress', 'completed', 'aborted');

create table interviews (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references profiles(id),
  type interview_type not null,
  jd_text text not null,
  resume_id uuid references resumes(id),
  status interview_status not null default 'setting_up',
  phase text,                            -- current phase name, type-specific
  started_at timestamptz,
  ends_at timestamptz,
  created_at timestamptz default now()
);

create table interview_transcripts (
  id uuid primary key default gen_random_uuid(),
  interview_id uuid references interviews(id),
  turn_index int not null,
  speaker text not null,                 -- 'ai' | 'user'
  text text not null,
  created_at timestamptz default now()
);

create table question_bank (
  id uuid primary key default gen_random_uuid(),
  type interview_type not null,
  question text not null,
  test_cases jsonb,                      -- [{input, expected_output}]
  tags text[],
  embedding vector(768),
  created_by uuid references profiles(id),
  created_at timestamptz default now()
);

create table interview_reports (
  id uuid primary key default gen_random_uuid(),
  interview_id uuid references interviews(id),
  report_data jsonb not null,            -- score, strengths/weaknesses, transcript summary
  created_at timestamptz default now(),
  expires_at timestamptz not null        -- created_at + 7 days
);
```

**Row-Level Security (RLS)**: enabled on every table. Baseline policy: a row is visible/editable only by its `user_id` owner, except:
- `question_bank` — readable by all authenticated users, writable only by Owner or Admins with the `manage_question_bank` permission.
- `roles` / `admin_permissions` — writable only by Owner.

**ATS checks are not persisted** — no table; scoring is request/response only.

---

## 6. BYOK System — Detailed Design

### 6.1 Provider adapter interface (`apps/api/app/providers/base.py`)
```python
class ProviderAdapter(ABC):
    async def validate(self, api_key: str) -> bool: ...
    async def chat(self, api_key, messages, stream=True, options: LLMOptions | None = None, usage: Usage | None = None) -> AsyncIterator[str]: ...
    async def embed_many(self, api_key, texts, usage=None, kind="doc"|"query") -> list[list[float]]: ...  # only Gemini implements this
```
`gemini.py` talks to Gemini's **REST API with httpx** (no SDK: the legacy SDK is deprecated, its successor conflicts with supabase's httpx pin, and REST gives per-request keys in a header, real timeouts, raw error bodies and thinking control). `claude.py` / `groq.py` use their SDKs with `max_retries=0` and explicit timeouts, so the gateway is the only retry layer. Every adapter maps provider failures to typed errors: `ProviderRateLimitError(kind=rpm|rpd, retry_after)`, `ProviderUnavailableError(retry_after)`, `ProviderTimeoutError`, `ProviderAuthError`, `ProviderBadRequestError`, `ProviderConfigError` (retired model), `ProviderBlockedError`. Adapters report `finish_reason`, model, thought tokens and time-to-first-token through `Usage`. Features never call adapters directly (see 6.4).

### 6.2 Key lifecycle
1. **Submit**: `POST /keys` `{ provider, slot, api_key }` → FastAPI encrypts (`Fernet`, server-held secret key from env) → stores in `provider_keys` with `is_valid = false`.
2. **Validate**: immediately after storing, call `adapter.validate(api_key)` (a minimal "hi" chat call) → update `is_valid` + `last_validated_at`. Return validation result synchronously to the UI so the user gets immediate feedback.
3. **List**: `GET /keys` → returns provider/slot/is_valid/last_validated_at (never the decrypted key itself).
4. **Delete/replace**: `DELETE /keys/{id}`, or resubmit same provider+slot to overwrite.
5. **Onboarding gate**: `(auth)/onboarding/page.tsx` blocks progression to the dashboard until a `provider=gemini, slot=primary` key exists with `is_valid = true`.

### 6.3 Runtime failover
Implemented once, in the gateway (6.4): primary key first; on a rate-limit/quota error, the backup key once (with a one-shot notification to the user); if both fail or there is no backup, a clear 429. Nothing is retried or failed over after streamed output has started.

### 6.4 LLM gateway (`apps/api/app/llm/`) -- all model traffic goes through it
```
gateway.py      complete()/complete_full()/complete_structured()/stream()/embed():
                cooldown check -> per-key limiter -> adapter (own timeout) -> jittered retry (honours Retry-After)
                -> backup-key failover -> usage record -> one structured log line; whole non-streaming call has a deadline
options.py      LLMOptions(task, caps, temperature, json_mode, timeout_s, feature, priority, prompt_id/version, trim_on_length, model_override), Usage
completion.py   Completion(text, finish_reason, usage, model, latency, attempts, failed_over)
models.py       task -> model, per-task timeouts, Gemini thinking/allowance traits, fallback list; the ONE place to fix a retired model
keystate.py     key fingerprints (limits are per key/project), cooldowns for spent keys, Pacific quota day, seconds-to-reset
limiter.py      per-KEY sliding-window RPM with priority lanes (background can't use the last quarter)
usage.py        daily totals per user/provider/kind (Gemini booked to the Pacific day) incl. thought tokens
schemas.py      pydantic shapes for every JSON the model returns; json_utils.extract_json (raw_decode)
untrusted.py    prompt-injection standard: data tags with random ids, sanitizers, reply filter
budget.py       estimate_tokens (chars/4), truncate, trim_to_sentence, fit_to_budget, ensure_user_first
prompts/        interview.py, ats.py, resume.py -- every prompt template lives here
```
Errors surface as `AppError` with stable codes: 412 `key_missing`, 429 `quota_exhausted`, 503 `provider_overloaded`, 503 `provider_misconfigured` (stale model name), 504 `provider_timeout`, 400 `key_rejected`, 422 `reply_blocked`, 502 `provider_bad_request` / `empty_reply` / `invalid_model_output`.

**Rules the gateway enforces**: never retry or fail over after streamed output began; per-key (not per-user) limits, because quota belongs to the key's project; a daily-quota (`rpd`) 429 benches the key until Pacific midnight and fails over immediately, a short per-minute (`rpm`) 429 is waited out once; thinking is kept minimal and its tokens are budgeted and reported; truncated replies are trimmed to whole sentences (or retried with room, for JSON); streaming usage and the chat exchange are recorded even if the client disconnects.

**Prompt rules**: static prefix first; terse imperative text; send only the current phase's instruction; cap output both in the prompt and with `max_output_tokens`; JSON via provider JSON mode + pydantic validation + one repair retry; never resend distilled data (JD -> `interviews.brief`, old turns -> incremental `running_summary`, resume -> `resumes.digest`); the first non-system message is always a user turn.

**Prompt-injection standard** (`llm/untrusted.py`): everything untrusted (JD, resume, digest, candidate answers, and anything *derived* from them) is wrapped in `<data kind=".." id="rand">..</data id="rand">` with a fresh id per request; the system prompt states that such text is data; brief and summary are never in the system role (they ride in the conversation as data) and are sanitized/capped before being stored; replies pass a verbatim-leak filter and label/tag cleanup. Covered by an offline injection corpus (`tests/test_prompt_injection.py`).

**Evidence over assumption**: wire formats were written from documentation; `scripts/llm_smoke.py` (owner-run, <=10 spaced requests, key from the environment) records real responses to `tests/fixtures/gemini/`, which `tests/test_recorded_fixtures.py` then replays through the adapter.

---

## 7. Authentication Flow — Detailed Design

**Decision**: Google is the *only* way to create or access a CyntraAI account — there is no email/password sign-up form. A password is introduced later, purely as a second login option, never as a registration method.

### 7.1 Flow
1. **Sign-in page** (`(auth)/sign-in/page.tsx`): a single "Continue with Google" button — no email/password fields at all. Uses Supabase Auth's Google OAuth provider (`supabase.auth.signInWithOAuth({ provider: 'google' })`).
2. **First-ever sign-in for a user** (detected via: no `profiles` row exists yet for this `auth.users.id`): after the OAuth redirect completes, route to `(auth)/account-setup/page.tsx` instead of the dashboard.
   - The page displays the Gmail address returned by Google **in a disabled/uneditable input** (pre-filled, styled clearly as read-only — not just a disabled attribute with no visual cue).
   - Below it, a **"Set a password"** tab/section: password + confirm-password fields, standard strength validation (`zod` schema: min length, at least one number/symbol).
   - On submit: call Supabase Auth's `updateUser({ password })` — this attaches a password credential to the same account, so `email` (from Google) + this password becomes a valid alternate credential pair from then on.
   - This also creates the `profiles` row (+ default `roles` row, per Phase 1 step 4) — this is the actual account-creation moment, gated behind having come from a real Google OAuth redirect.
3. **Subsequent sign-ins**: the sign-in page still only shows "Continue with Google" as the primary action, but since a password now exists, a secondary **"Sign in with email & password instead"** link/tab is available for returning users who prefer it — using the same Gmail address (uneditable/known) + their set password.
4. **Post account-setup**: user proceeds to `(auth)/onboarding/page.tsx` (Phase 2 — mandatory Gemini key step) before reaching the dashboard.

### 7.2 Why this shape
- Removes password-reuse/phishing risk of a traditional sign-up form entirely — every account is guaranteed to originate from a real Google identity.
- Still gives users a fallback login method (useful if Google OAuth has an outage, or the user prefers not to re-auth via Google every time) without ever letting *that* password be the way an account is created.

### 7.3 Implementation notes
- Supabase Auth natively supports attaching a password to an OAuth-created user via `updateUser`, so no custom auth system is needed — this stays within Supabase Auth's built-in capabilities.
- `lib/auth/guards.ts` (Phase 1) should treat "has a `profiles` row" as the source of truth for "has completed account setup," redirecting anyone who authenticated via Google but hasn't finished `account-setup` back to that page before anything else (including onboarding).

---

## 8. UI/UX Design System — Detailed Design

**Goal**: CyntraAI should feel like a polished, premium product — both light and dark themes fully supported, smooth transitions throughout, and tasteful 3D visuals specifically where they add value (loading/setup screens), not scattered everywhere.

### 8.1 Theming (light + dark)
- `next-themes` drives theme state (`system` / `light` / `dark`), persisted via its own cookie/localStorage handling.
- Tailwind configured with `darkMode: 'class'`; all colors defined as CSS variables/design tokens (e.g. `--bg-primary`, `--text-primary`, `--accent`) with a light and dark value each, rather than hardcoded Tailwind color classes scattered through components — keeps future palette changes to one place.
- `components/ui/ThemeToggle.tsx` — accessible toggle (sun/moon), available in the dashboard nav and on auth pages.
- Every component built from Phase 1 onward must be checked in both themes as part of its own "definition of done," not fixed retroactively in Phase 10.

### 8.2 Transitions
- `framer-motion` for: page/route transitions (dashboard section switches), modal/dialog enter-exit, list item add/remove (e.g. chat messages appearing, resume list updates), and micro-interactions (button press states, toggle switches).
- Voice interview state changes (listening → thinking → speaking) get deliberate, smooth animated transitions in `VoicePanel.tsx` — this is a key "feel" moment for the product's flagship service.

### 8.3 3D Visuals
- `three` + `@react-three/fiber` + `@react-three/drei` for WebGL 3D scenes, isolated behind reusable components in `components/three/`.
- **Primary use case**: the ~5-minute "setting up your interview" loading screen (Phase 6) — an ambient, tasteful animated 3D scene (e.g. a slowly rotating abstract object, particle field, or similar) combined with the progressive status messages from Phase 10 step 1, rather than a generic spinner.
- Kept intentionally scoped to loading/setup moments, not applied to core functional UI (chat, coding editor, transcript) where a 3D visual would be a distraction rather than a delight — 3D is a moment of polish during otherwise "dead" wait time, not a persistent motif.
- Built as an isolated, lazy-loaded component (dynamic import, `ssr: false`) so it never impacts the initial load performance of functional pages.

### 8.4 Where this lands in the build plan
- **Phase 1** gains a design-system foundation step (theme tokens, `ThemeProvider`, base `framer-motion` setup, and a first placeholder `LoadingScene.tsx`) so every subsequent phase builds UI against the real system instead of ad hoc styling that gets reworked later.
- **Phase 6** (interview setup flow) is where the 3D loading scene gets its real, finished treatment, tied to actual setup progress.
- **Phase 10** (Polish Pass) is where transitions, theme consistency, and the 3D loading experience get their final refinement sweep across the whole app — not where they're introduced for the first time.

---

## 9. Phase-by-Phase Build Plan

### Phase 1 — Foundation
**Goal**: a running skeleton with auth, roles, and empty pages wired end-to-end.

1. Scaffold monorepo: `apps/web` (`create-next-app`, TypeScript, App Router, Tailwind), `apps/api` (FastAPI + `uvicorn`, `requirements.txt`).
2. Create Supabase project; run the schema migration from Section 5 (as SQL files in `apps/api/migrations/`); enable `pgvector` extension; enable RLS + policies.
3. Enable the **Google provider** in Supabase Auth (OAuth client ID/secret from Google Cloud Console); wire `@supabase/ssr` into Next.js with session middleware.
4. Build the auth flow from Section 7: `(auth)/sign-in/page.tsx` ("Continue with Google" only) → `(auth)/account-setup/page.tsx` (uneditable Gmail display + set-password form, only shown when no `profiles` row exists yet for the user) → on submit, call `updateUser({ password })` and create the `profiles` + `roles` rows. **First user ever created becomes Owner automatically**; all subsequent accounts default to `user` (Owner/Admin promote them later via the team settings page).
5. Build `lib/auth/guards.ts` — helper to check role/permission in Route Handlers and Server Components (e.g. `requireRole('owner')`, `requirePermission('manage_question_bank')`), plus the "must complete account-setup before anything else" redirect rule from Section 7.3.
6. Set up Cloudflare R2 bucket; add credentials to both apps' env config; write a small `lib/storage.ts` (web) and `core/storage.py` (api) wrapper around the S3-compatible client for upload/download URLs.
7. FastAPI: implement JWT verification middleware (`core/security.py`) that validates the Supabase-issued JWT on every request and extracts `user_id` + role.
8. **Design-system foundation** (Section 8): Tailwind dark-mode/class config + color tokens for light and dark, `next-themes` `ThemeProvider`, `components/ui/ThemeToggle.tsx`, base `framer-motion` setup for page/element transitions, and a first placeholder `components/three/LoadingScene.tsx` (lazy-loaded, `ssr: false`) — every UI piece built from this point on is built against this system, not ad hoc styling.
9. Build the dashboard shell (`(dashboard)/layout.tsx`) with nav placeholders for all five sections (Chat, Interviews, ATS Score, Resumes, Settings) — pages can be empty/stubbed, but themed and animated per the design system.
10. **Definition of done**: a user can sign in with Google, complete account setup (see their Gmail, set a password), land in an empty but fully themed dashboard (light/dark both correct), toggle theme with a smooth transition, and the FastAPI health-check endpoint (`GET /health`) is reachable and validates a forwarded JWT correctly.

### Phase 2 — BYOK System
**Goal**: users can add, validate, and manage provider keys; onboarding enforces the mandatory Gemini key.

1. Write `provider_keys` migrations (already in Section 5) if not applied in Phase 1.
2. Implement `core/security.py::encrypt_key` / `decrypt_key` using `cryptography.fernet.Fernet` with a server-side secret from env (never logged, never returned to client).
3. Implement `providers/base.py` interface and `providers/gemini.py`, `providers/claude.py`, `providers/groq.py` using each vendor SDK, each implementing `validate()` as a minimal low-token "hi" call.
4. Implement `keys/router.py`: `POST /keys`, `GET /keys`, `DELETE /keys/{id}`.
5. Implement `keys/service.py::call_with_failover` (Section 6.3) — write unit tests mocking a rate-limit exception to confirm failover triggers correctly.
6. Build `(auth)/onboarding/page.tsx`: step 1 (mandatory) Gemini key form with inline "how to get your Gemini API key" instructions + live validation feedback; step 2 (optional, skippable) Groq/Claude key forms, each with their own instructions; backup-key inputs available for each provider.
7. Build `settings/api-keys/page.tsx` for post-onboarding management (add/replace/delete keys, see validity status).
8. Add route-guard middleware: any dashboard route beyond onboarding checks for a valid primary Gemini key and redirects back to onboarding if missing.
9. **Definition of done**: a new user cannot reach the dashboard without a validated Gemini key; adding a bad key shows a clear inline error; adding a backup key and simulating a primary rate-limit (via a test flag or mocked exception) demonstrably fails over.

### Phase 3 — AI Chatbot Service
**Goal**: full chat round-trip using any configured provider, streamed to the UI.

1. `chat/router.py`: `POST /chat/{conversationId}/messages` — accepts a message, loads recent history (simplest: full history for chat, no summarization needed here since chats are shorter-lived and per-conversation, unlike interviews), calls `adapter.chat()` via `call_with_failover`, streams tokens back (Server-Sent Events or chunked response).
3. Minimal `conversations` + `messages` tables (add to schema if chat history should persist — confirm persistence requirement; default assumption: yes, persisted per user, simple two-table addition mirroring the pattern already used elsewhere).
4. Frontend: `chat/page.tsx` (conversation list), `chat/[conversationId]/page.tsx` (message thread), `components/chat/ChatWindow.tsx` with streaming render (append tokens as they arrive).
5. Model/provider selector in the chat UI, restricted to providers the user has a valid key for.
6. **Definition of done**: a user picks a provider, sends a message, receives a streamed response; switching providers mid-conversation works; a simulated rate-limit on the active key triggers failover without the user seeing a broken response.

### Phase 4 — RAG Foundation
**Goal**: shared parsing/embedding/retrieval pipeline ready for both Interviewing Agent and ATS Score.

1. `rag/parsing/pdf.py` (via `pdfplumber`) and `docx.py` (via `python-docx`) — extract raw text from uploaded resumes/JD files.
2. `rag/chunking.py` — simple fixed-size or section-aware chunking (split on headings like "Experience", "Education", "Skills" when detectable, fallback to fixed-token windows).
3. `rag/embeddings.py` — always calls the Gemini adapter's `embed()` regardless of the user's selected chat provider (per Section 6.1); batches chunk embedding calls.
4. `rag/retrieval.py` — pgvector cosine-similarity queries via the `match_resume_chunks`/`match_question_bank` Postgres RPC functions (see Section 5) against `resume_chunks.embedding` and `question_bank.embedding`.
5. Resume upload flow: `resumes/page.tsx` lets users upload a PDF/DOCX → Next.js Route Handler (`app/api/resumes/route.ts`) uploads raw file to R2 (`resumes/<user_id>/<resume_id>.<ext>`, stored as `resumes.file_key`) → calls FastAPI `POST /rag/resumes/{id}/process`, which downloads the file back from R2, parses/chunks/embeds it, and stores the result in `resumes.parsed_text` + `resume_chunks`.
6. **Definition of done**: uploading a resume produces a stored `parsed_text` and `resume_chunks` rows with non-null embeddings; a test query against a sample JD returns semantically relevant resume chunks ranked correctly.

### Phase 5 — ATS Score Service
**Goal**: full scoring pipeline with sub-scores and feedback.

1. `ats/requirements_extractor.py` — LLM call (via failover-wrapped provider call, using whichever chat provider the user has configured, or default to Gemini) that returns structured JSON: `{must_have: [...], nice_to_have: [...], experience_level, title}`.
2. `ats/scorer.py`:
   - `keyword_score()` — exact + simple synonym matching (small curated synonym map to start; can be extended later) between extracted requirements and resume text.
   - `semantic_score()` — uses `rag/retrieval.py` to match each requirement against resume chunks, averaging best-match similarity scores.
   - `formatting_score()` — heuristic checks on the parsed structure (e.g. did `pdf.py` detect multi-column text ordering issues, are standard section headers present, is contact info detectable) — deduct for detected issues.
   - `composite_score()` — weighted average (e.g. 40% keyword, 40% semantic, 20% formatting — tunable) producing 0–100.
3. `ats/feedback.py` — LLM call that turns the raw sub-scores + gaps into a written, actionable summary.
4. `ats/router.py`: `POST /ats/score` `{ resume_id, jd_text }` → runs the full pipeline synchronously (or with a lightweight polling/progress state if it's slow) → returns `{ composite_score, keyword_score, semantic_score, formatting_score, feedback }`. No persistence.
5. Frontend: `ats-score/page.tsx` — resume selector + JD textarea → submit → `components/ats/ScoreBreakdown.tsx` renders the composite score plus each sub-score and the written feedback.
6. **Definition of done**: running a real resume against a real JD produces a sensible composite score, visibly different sub-scores, and coherent written feedback; a badly-formatted resume (e.g. table-heavy) visibly scores lower on formatting.

### Phase 6 — Interviewing Agent: Orchestration Core (text-only, no voice yet)
**Goal**: a complete mock interview can be run end-to-end via text before voice is layered on.

1. Question bank admin CRUD: `interviews/question_bank.py` + `admin/question-bank/page.tsx` — Owner/Admin (with permission) can create/edit/delete questions with test cases, tagged by interview type; each question embedded on save (reuses `rag/embeddings.py`).
2. `interviews/orchestrator.py` — a state machine per interview: `setting_up → phase_1 → phase_2 → ... → wrap_up → completed`. Each interview `type` module (`types/coding.py`, `types/behavioral.py`, etc.) defines its own ordered phase list + time allocation per phase (e.g. coding: `[('intro', 5), ('problem_1', 40), ('problem_2', 10), ('wrap_up', 5)]`).
3. Setup flow: `interviews/setup/page.tsx` — select resume, paste JD → `POST /interviews` creates a row (`status = setting_up`) → backend kicks off: parse/chunk/embed JD (reusing Phase 4 pipeline), RAG-select 2 questions from `question_bank` (for types that need them), build a personalized opening-question plan → once ready, flip `status = in_progress`, `started_at = now()`, `ends_at = now() + 1hr`. Frontend polls or subscribes (Supabase Realtime) for the status flip to move past the "setting up" loading screen. This is where `components/three/LoadingScene.tsx` (Section 8.3) gets its real, finished 3D treatment, paired with progressive status messages tied to actual backend progress (e.g. "Analyzing your resume…" → "Matching questions to the job description…").
4. `interviews/summarizer.py` — after each turn, append to `interview_transcripts`; maintain a running summary (re-summarize every N turns via a small LLM call) so subsequent prompts to the LLM include the summary + last few raw turns, not the full history — keeping token usage flat.
5. `interviews/router.py`: `POST /interviews`, `GET /interviews/{id}`, `POST /interviews/{id}/turns` (text-mode: user submits an answer, gets the AI's next question/follow-up back), `POST /interviews/{id}/complete`.
6. Wire `call_with_failover` for every LLM call in this service, scoped to Gemini/Groq only (Claude excluded per decision).
7. Frontend: `interviews/[interviewId]/page.tsx` in text-only mode first — a chat-like transcript view + phase/timer display (`components/interview/PhaseTimer.tsx`) — to validate orchestration before voice UI is built.
8. **Definition of done**: a full 1-hour (or accelerated-for-testing) mock interview can be run start to finish in text mode, phases advance correctly with the timer, questions are visibly personalized to the resume/JD, and a simulated rate-limit mid-interview fails over without breaking the session.

### Phase 7 — Interviewing Agent: Coding Platform
**Goal**: coding-type interviews get a live code editor with test-case execution.

1. `coding/judge0_client.py` — thin async client for the hosted Judge0 API (submit code + language + stdin, poll for result, map to pass/fail against each test case).
2. Extend `interviews/router.py`: `POST /interviews/{id}/submissions` `{ code, language }` → runs against the current question's `test_cases`, returns per-test pass/fail + stdout/stderr.
3. Frontend: `components/interview/CodeEditorPanel.tsx` using `@monaco-editor/react`, split-screen with `TranscriptPanel.tsx`/`VoicePanel.tsx`; a "Run" button showing test results inline.
4. Wire the coding-type interview phases (`types/coding.py`) to present the RAG-selected question + starter code template alongside the editor.
5. **Definition of done**: during a coding-type interview, the user can write code, run it against visible test cases, and see pass/fail feedback, with the AI able to reference the submission in its follow-up questions.

### Phase 8 — Interviewing Agent: Voice Layer
**Goal**: the full voice-driven experience — the hardest, most important part of the product — built last since it depends on stable orchestration underneath.

1. `interviews/voice/ws_handler.py` — a FastAPI WebSocket endpoint per interview session; browser streams audio chunks up, server streams TTS audio + partial transcripts down.
2. `interviews/voice/stt.py` — routes audio to Groq's Whisper-based STT (fast) or Gemini's native audio understanding, wrapped in `call_with_failover`; returns incremental/streamed transcripts.
3. `interviews/voice/tts.py` — converts the AI's next question/response text to speech via whichever of Gemini/Groq supports it at call time; streamed back to the client as playable audio chunks.
4. `interviews/voice/vad.py` — voice activity detection (e.g. `webrtcvad` or a lightweight energy-based approach as a first pass) to detect end-of-turn vs. thinking-pause; defines the "long silence" edge-case handling (e.g. after N seconds of silence, AI gently prompts "take your time" or moves on based on phase time budget).
5. Frontend: `components/interview/VoicePanel.tsx` — mic capture (Web Audio API / `MediaRecorder`), WebSocket connection lifecycle, playback of streamed TTS audio, visual state (listening / thinking / speaking), reconnect handling on transient network drops (buffer + resume rather than losing interview state, since `interview_transcripts` is the durable source of truth).
6. Integrate with `TranscriptPanel.tsx` so the live transcript renders chunk-by-chunk in sync with audio.
7. **Definition of done**: a full mock interview can be conducted entirely by voice — AI speaks, user responds by talking, transcript renders live, silence/interruption edge cases behave sensibly, and a brief network drop recovers without losing interview progress.

### Phase 9 — Reports
**Goal**: post-interview report generation, time-boxed availability, and cleanup.

1. On `interviews/{id}/complete`, generate report content (LLM call summarizing performance from `interview_transcripts` + phase outcomes + coding submission results if applicable) → store in `interview_reports` with `expires_at = now() + 7 days`.
2. `reports/router.py`: `GET /reports/{interviewId}` (view), `GET /reports/{interviewId}/download` (PDF or structured export) — both check `expires_at` before serving.
3. `reports/cleanup_job.py` — an `apscheduler` job (or Supabase scheduled Edge Function, whichever proves simpler in Phase 1's infra setup) running daily, deleting rows where `expires_at < now()`.
4. Frontend: `reports/page.tsx` — list of available reports with a visible countdown to expiry and a download button.
5. **Definition of done**: completing an interview produces a downloadable report; after the 7-day mark (simulate by backdating `expires_at` in a test), the report is no longer accessible and is actually purged by the cleanup job.

### Phase 10 — Polish Pass
**Goal**: production-quality feel across the hardest-to-get-right surfaces.

1. Final refinement sweep on theming, transitions, and the 3D loading experience (Section 8.4) across every page built in Phases 1–9 — not introduced here for the first time, just polished and made consistent (e.g. any page that slipped through with hardcoded colors instead of design tokens gets fixed).
2. Refine the live interview room's visual/interaction polish (voice state indicators, phase progress bar, smooth transcript auto-scroll, `framer-motion` transitions on state changes per Section 8.2).
3. Sweep all services for consistent error states (expired key, both keys exhausted, network drop, malformed resume upload) with clear, non-technical user-facing messaging, correctly themed in both light and dark mode.
4. Accessibility pass on voice-heavy UI (captions always visible as a fallback, keyboard navigation for the coding platform, reduced-motion support for users who disable animations).
5. **Definition of done**: a full walkthrough of all three services, and the BYOK onboarding, feels cohesive and professional in both themes, with smooth transitions throughout and a polished 3D loading experience — this is the final gate before considering v1 complete.

---

## 10. Verification Approach

- **Backend**: pytest per module (`test_keys.py`, `test_chat.py`, `test_rag.py`, `test_ats.py`, `test_interviews.py`) — provider adapters mocked for unit tests (including forced rate-limit exceptions to test failover); a real developer BYOK key used for integration smoke tests against actual providers.
- **Frontend**: manual QA in-browser after each phase — golden path plus deliberate edge cases (bad key, expired report, silence during voice interview) tested live, not assumed from code alone.
- **End-to-end checkpoints** (must pass before moving to the next phase):
  - After Phase 3: full chat round-trip with a real key, including a forced-failover test.
  - After Phase 6: a full mock interview run text-only, correct phase/timer progression, personalized questions confirmed.
  - After Phase 8: a full mock interview run entirely by voice, including a deliberate silence and a deliberate network drop.
- Testing is introduced starting Phase 1 (pytest scaffolding + a first Playwright smoke test for sign-up/onboarding), not bolted on at the end.

---

## 11. Status

**Planning complete. Awaiting explicit approval before any code is written.**
