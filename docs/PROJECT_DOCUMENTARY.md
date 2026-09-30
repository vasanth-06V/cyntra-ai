# CyntraAI — Project Documentary

This is the running build log for CyntraAI. Unlike [IMPLEMENTATION.md](IMPLEMENTATION.md), which is the fixed plan, this file is a **chronological journal** of what was actually done, in what order, and what went wrong along the way.

**Rule going forward**: after every executed step (a command run, a file created/edited, a service configured, a bug hit and fixed), an entry is appended here — what was done, why, the exact commands/files involved, the outcome, and any problems encountered plus how they were resolved. Nothing gets summarized away or skipped, even minor steps.

---

## How entries are logged

Each entry follows this shape:

```
### [YYYY-MM-DD] <Phase N — short title>

**Action**: what was executed (commands, files created/edited, config changed)
**Why**: the reason this step was needed
**Result**: what happened — success, output, current state after this step
**Problems faced**: any errors, blockers, or unexpected behavior — and exactly how each was diagnosed and fixed. If none, state "None."
```

Entries are appended in chronological order, oldest first. Nothing is edited or deleted retroactively except to correct a factual error in a past entry (marked as a correction, not a silent edit).

---

## Log

### [2026-09-27] Planning Phase — Idea, feature scope, and architecture finalized

**Action**: A full discussion-in-a-loop process with the user (per their explicit requested workflow: discuss → finalize features → write detailed implementation plan → get approval → only then implement). Below is the complete detail of everything covered and decided.

**Why**: The user wanted to redesign CyntraAI from scratch (a prior version of the project had been intentionally erased) and required the whole scope to be discussed and locked down before any code is written, so this documentary preserves that reasoning for later reference.

**Result**: Two documents produced — `docs/IMPLEMENTATION.md` (the fixed plan) and this file. Full detail of what was decided follows.

---

#### 1. Origin / context reset
- The prior CyntraAI project (with its own locked palette, test baseline, git history, etc.) had been intentionally erased by the user. All old memory referencing that project (overview, workflow feedback, test account, UI constraints) was identified as stale and deleted at the user's explicit request, so nothing from the old build biases this fresh design.

#### 2. Platform concept
- CyntraAI is a **single-tenant** AI platform (not multi-org/multi-tenant) offering multiple pluggable services under one account system.
- **User roles**: **Owner** (full control), **Admin** (custom permissions individually granted by the Owner — not a fixed permission set), **Application User** (standard end user).

#### 3. BYOK (Bring Your Own Key) system — the platform's core cost model
- Users provide their own LLM API keys rather than the platform paying for LLM usage.
- Initial supported providers: **Gemini, Claude, Groq** (architecture designed to add more providers later without rework).
- **Gemini is mandatory** — it is required to complete onboarding, because it powers embeddings platform-wide (used by both the RAG pipeline in the Interviewing Agent and the ATS Score service). This became necessary once we determined that Groq and Claude do not offer embedding APIs at all, only Gemini does among the three — so any RAG-dependent feature has a hard dependency on a valid Gemini key regardless of which provider a user prefers for chat.
- Claude and Groq are **optional** add-ons.
- Each provider supports **two key slots**: primary + backup.
- **Key validation flow**: user pastes a key into a guided form (with per-provider instructions on how to obtain that key) → key is sent once to the backend → backend encrypts and stores it → backend sends a minimal test message ("hi") to the provider using that key → validity is confirmed or rejected, shown to the user immediately. This was deliberately designed as **server-side** validation (not client-side) so the raw key never has to live in the browser beyond the initial submission, and the same code path used for validation is reused for real chat calls later.
- **Encryption**: keys are encrypted at rest — never stored or logged in plaintext.
- **Automatic failover**: if a user's primary key for a provider hits a rate limit / quota exhaustion mid-session, the system automatically and silently switches to that provider's backup key so the user's current activity (chat, interview, ATS check) is not interrupted. Only *after* the switch does the user get notified (e.g. "your primary Gemini key hit its limit, now using your backup key"). A hard error is only shown if both keys fail. This was specifically motivated by the Interviewing Agent's requirement that a live interview must never break mid-session due to a rate limit.
- **Architecture**: each provider gets its own adapter module behind a shared interface (`chat()`, `embed()`, `validate()`), so orchestration code never has to special-case a specific provider.

#### 4. Service 1 — AI Chatbot
- The simplest of the three services: a chat interface where the user picks any of their configured, valid providers (Gemini/Claude/Groq) and converses with that model.
- Deliberately planned to be built **first** (after the BYOK system itself), specifically to validate the provider-adapter and key-failover plumbing end-to-end before the harder two services are built on top of the same foundation.

#### 5. Service 2 — AI Interviewing Agent (the most complex service — "the heart of the platform")
- **Interview types**, each with its own dedicated pipeline: Coding, Behavioral, HR, ML/AI, Web Dev, SDE, System Design, Case Study/Product Sense. (System Design and Case Study were added to the user's original list of six after discussion, and accepted.)
- **Per-interview setup**: the user selects a previously saved resume (managed in a dedicated Resumes section of settings) and pastes a job description **specific to that interview** — JD is never fixed/reused, it's provided fresh each time. After submission, a **~5 minute "setting up your interview" phase** runs with a polished loading UI (later decided to include a tasteful 3D visual — see the UI/UX section below) while the backend works in the background.
- **RAG pipeline**: the resume and JD are parsed (PDF/DOCX), chunked, and embedded (via the mandatory Gemini key) into a vector store. This is used both to personalize the interview's questions/follow-ups to the candidate's actual background, and to select the most relevant questions from a maintained question bank.
- **Coding platform**: for interview types that need it, a live code editor is presented alongside the interview, pre-loaded with 2 questions selected via the RAG pipeline (each question stored with its own test cases). Submitted code runs against those test cases in a sandboxed execution environment.
- **Question bank**: maintained by the Owner, and by Admins if granted that specific permission — not open to regular users.
- **Fixed duration**: exactly 1 hour per interview, split into distinct phases — the phase breakdown differs per interview type (e.g. a coding interview's phases differ from a behavioral interview's phases).
- **Voice-driven experience — explicitly called out by the user as the heart of this entire service**: the AI speaks its questions (text-to-speech) while also displaying the text on screen; the candidate's spoken answers are transcribed (speech-to-text) and displayed on screen chunk-by-chunk as they're recognized, not just at the end. Edge cases like long silence and interruptions need explicit handling (voice activity detection) so the experience never feels broken or awkward.
- **Restricted to Gemini + Groq only** for this service specifically — Claude was excluded here because it offers no native audio (TTS/STT) support, and Gemini/Groq were judged better suited to real-time, long-running sessions (Gemini's large context window, Groq's very fast inference).
- **Token/context management is a first-class concern**: because BYOK keys typically come with low rate limits / low tokens-per-minute, the interview pipeline must avoid replaying the full conversation transcript on every LLM call. Instead, a running summary of the conversation is maintained server-side, combined with RAG-based retrieval of only the relevant resume/JD/question context per turn — explicitly framed by the user as "prompt engineering is part of this." Combined with the automatic key failover described above, the goal is that an interview should never break or stall mid-session regardless of rate limits.
- **Mode**: timed formal mode only for now; an untimed practice mode was discussed and explicitly deferred to a later phase.
- **Post-interview report**: generated after completion, made available for **download for exactly 7 days**, after which it is no longer accessible and gets purged by a scheduled cleanup job. No session recording/playback (explicitly declined). No anti-cheating detection such as tab-switch monitoring (explicitly deferred, not needed for the current self-practice framing of the product).

#### 6. Service 3 — AI Resume ATS Score
- Purpose: score how well a resume matches a given job description, similarly to how real-world Applicant Tracking Systems evaluate resumes, but reimplemented by CyntraAI using a RAG-based approach.
- Research into how real ATS systems work informed the design: they rely on (a) keyword/skill matching against the JD, (b) parseability — many real ATS engines fail to correctly read resumes with tables, multi-column layouts, images, or non-standard section headers, which is a distinct scoring dimension separate from content relevance, and (c) semantic relevance beyond exact keyword overlap.
- **Reuses** the same resume storage/parsing pipeline as the Interviewing Agent (upload once, use everywhere) — confirmed explicitly by the user.
- **Scoring pipeline**: (1) JD is parsed into structured requirements via an LLM call (must-have skills, nice-to-have skills, experience level, title); (2) a keyword coverage score is computed (exact + synonym matching); (3) a semantic similarity score is computed via embeddings/RAG matching between resume chunks and JD requirements; (4) a formatting/parseability check flags structural issues that would break a real ATS; (5) a weighted composite score (0–100) is produced, **with all three sub-scores shown to the user**, not just the final number (explicitly requested); (6) an LLM generates actionable written feedback (missing keywords, rephrasing suggestions, formatting fixes).
- Embeddings for this service always go through Gemini specifically, which is part of why the Gemini key was made mandatory platform-wide rather than optional.
- **No history is persisted** — each ATS check is a one-off, ephemeral result, explicitly decided against storing a history table for this service.

#### 7. Tech stack decisions (with reasoning)
- **Frontend**: Next.js (TypeScript, App Router) on Vercel (free tier) — decided early and never revisited.
- **Backend split**: rather than one backend language, the platform uses Next.js Route Handlers/Server Actions for lightweight CRUD (auth-adjacent work, settings, role management, resume metadata, question bank admin CRUD) and a separate **Python 3.11 + FastAPI** service for everything AI/RAG-heavy (provider adapters, key management, RAG pipeline, interview orchestration, voice streaming, ATS scoring). This resolved the user's initial vague idea of "Python backend with JavaScript" into a concrete two-layer split, chosen because Python's ecosystem for document parsing (PDF/DOCX), embeddings/RAG tooling, and audio pipeline glue code is meaningfully stronger than JavaScript's, and those are exactly the two hardest services being built.
- **Database/Auth**: Supabase Postgres, chosen for its built-in **pgvector** support (avoiding a separate vector database entirely) plus Auth in one product.
- **File storage**: originally planned to use Supabase Storage, but switched to **Cloudflare R2** once the user flagged that Supabase's free storage tier (1GB) is too small for resume/report files at scale — R2's free tier offers 10GB, permanently (not a time-limited trial like AWS S3), with zero egress fees.
- **Cache**: Redis (via Upstash) was initially planned, but the user explicitly said no cache is needed for now — removed from the stack; rate-limiting and ephemeral session state will live in Postgres/in-memory instead, with Redis reintroduced later only if scale demands it.
- **Code execution** (for the coding interview platform): rather than self-hosting Judge0 (which needs real Docker/VM infrastructure that doesn't fit free serverless-style hosting), the plan uses **Judge0's free hosted API tier via RapidAPI** — zero infrastructure to manage, at the cost of accepting its free-tier rate limits for now.
- **Everything above was explicitly constrained to be free** — the user's only hard requirement on infrastructure choice. The resulting stack runs at $0/month; only LLM usage costs exist, and those are borne entirely by end users via BYOK.
- **Repo structure**: a single monorepo (`apps/web` + `apps/api`) rather than separate repositories, for simplicity.

#### 8. Authentication flow
- **Google OAuth is the only way to create or access an account** — there is no traditional email/password sign-up form at all.
- On a user's first-ever sign-in via Google, they land on an account-setup step showing their Gmail address in a **read-only/uneditable field**, plus a section to **set a password**.
- That password does **not** serve as a registration mechanism — it exists purely as an **alternate login method** going forward (confirmed explicitly via direct questions to the user), so a returning user can choose to sign in either via Google again or via their email + that password. This was designed to be implementable natively through Supabase Auth (attaching a password credential to an OAuth-created user via `updateUser`), with no custom auth system required.

#### 9. UI/UX direction
- The user was explicit that they want the **best possible UI/UX**, calling this out as a priority in its own right, alongside functional correctness.
- **Both light and dark themes** must be fully supported.
- **Nice transitions** throughout the app — decided to use `framer-motion` for page/element transitions and micro-interactions, with particular attention to the voice interview's listening/thinking/speaking state changes since that's the flagship interaction of the product.
- **3D visuals** specifically requested for "required areas like loading pages before interview" — decided to use `three` + `@react-three/fiber` + `@react-three/drei`, deliberately scoped **only** to loading/setup moments (like the ~5 minute interview setup screen) rather than applied throughout the app, so it reads as a moment of polish during dead wait time rather than a distracting motif across core functional UI (chat, coding editor, transcript).
- These decisions were folded into `IMPLEMENTATION.md` as a dedicated UI/UX Design System section, with the design-system foundation (theme tokens, ThemeProvider, base motion setup, placeholder 3D loading scene) scheduled into Phase 1 of the build so every subsequent phase is built against the real system rather than ad hoc styling reworked later.

#### 10. Documents produced from this discussion
- `docs/IMPLEMENTATION.md` — the fixed, detailed implementation plan (architecture, full folder structure, complete Supabase schema, BYOK detailed design, authentication flow, UI/UX design system, a 10-phase build plan each with concrete sub-steps and a definition of done, and a verification approach).
- `docs/PROJECT_DOCUMENTARY.md` (this file) — the chronological build journal, to be appended to after every executed implementation step going forward, including problems faced and how they were resolved.

**Problems faced**: None — this was entirely a planning/discussion phase; no code has been executed yet.

---

### [2026-09-30] Phase 1 — Monorepo scaffold, Supabase project, and schema

**Action**:
1. Created `apps/` and scaffolded `apps/web` via `create-next-app` (TypeScript, App Router, Tailwind, ESLint, npm). It auto-initialized its own nested git repo — removed (`rm -rf apps/web/.git`) since the monorepo needs a single root-level repo.
2. Manually scaffolded `apps/api` (FastAPI): created the full package structure (`app/core`, `app/providers`, `app/keys`, `app/rag/parsing`, `app/chat`, `app/interviews/{types,voice}`, `app/coding`, `app/ats`, `app/reports`, `migrations/`, `tests/`) with `__init__.py` in every package.
3. Wrote `requirements.txt`, `app/core/config.py` (pydantic-settings), `app/core/security.py` (Fernet encrypt/decrypt for BYOK keys + Supabase JWT verification via `get_current_user`), `app/core/db.py` (Supabase client factory), and `app/main.py` (FastAPI app with CORS + `/health` and `/health/authenticated`).
4. Created a Python venv (`apps/api/venv`) and installed dependencies.
5. Ran both dev servers to confirm they boot: `uvicorn app.main:app` → `GET /health` returned `{"status":"ok",...}`; Next.js dev server via the browser-preview tool → default starter page rendered correctly.
6. Created `.claude/launch.json` (dev-server launch config for both apps) and root `.gitignore`; ran `git init` at the monorepo root and staged all files (not committed — commits only happen when explicitly requested).
7. Created a new dedicated Supabase project (`cyntra-ai`, id `erdsnljuppltvmvivugv`, region `ap-south-1`) via the Supabase MCP tools, in the user's existing organization. Confirmed cost was $0/month before creating it.
8. Wrote and applied 6 migrations directly against the live project: enable `pgvector`; `profiles`/`roles`/`admin_permissions`; `provider_keys`; `resumes`; `interviews`/`interview_transcripts`/`question_bank`/`interview_reports`; and RLS policies + two SQL helper functions (`is_owner`, `has_admin_permission`) for role/permission checks.
9. Ran the Supabase security + performance advisors after migrating and found real issues (see Problems faced) — fixed all of them via two more migrations, then re-ran both advisors to confirm a clean result.
10. Generated a Fernet key for BYOK key-at-rest encryption and wrote `apps/api/.env` with the real Supabase project URL + generated encryption secret; service role key and JWT secret left as placeholders (Supabase doesn't expose these via the MCP API — needs manual retrieval from the dashboard).

**Why**: Phase 1's goal is a running skeleton with auth, roles, and empty pages wired end-to-end, per `docs/IMPLEMENTATION.md` Section 9.

**Result**: Monorepo structure exists and both apps boot locally. Supabase project is live with the full schema from the plan, RLS enabled on every table, and a clean bill of health from both the security and performance advisors. Local `.env` partially filled in — blocked on two values only available from the Supabase dashboard UI (service role key, JWT secret) and on Google OAuth client setup (needs Google Cloud Console, no MCP access available for that).

**Problems faced**:
- `pip install` failed on first attempt: `httpx==0.28.1` conflicted with `supabase==2.10.0`'s requirement of `httpx<0.28`. Fixed by pinning `httpx==0.27.2` in `requirements.txt`.
- First `create_project` call failed with a cost-confirmation mismatch error — the tool requires calling `get_cost` then `confirm_cost` with the exact returned amount before `create_project` will accept the confirmation ID. Fixed by following that exact sequence.
- After the first security-hardening migration, the Supabase security advisor flagged 4 real issues: mutable `search_path` on the two helper functions, the `vector` extension installed in the `public` schema, and both helper functions being callable as public PostgREST RPC endpoints (`anon` and `authenticated` roles). Fixed by moving `vector` to the `extensions` schema, moving the helper functions into a new `private` schema (not exposed by PostgREST's default schema list) with a pinned `search_path`, and revoking `EXECUTE` from `public`/`anon`/`authenticated`.
- That revoke was too aggressive and broke RLS: a policy's function call still requires the *querying* role to hold `EXECUTE` on the function, even though the function itself runs as `SECURITY DEFINER` — revoking `EXECUTE` from `authenticated` would have made every policy that calls `is_owner()`/`has_admin_permission()` fail for real signed-in users. Caught this before it caused a live failure by inspecting `information_schema.routine_privileges` after the revoke, then re-granted `EXECUTE` to `authenticated` specifically (kept revoked for `anon`/`public`) in a follow-up migration.
- The performance advisor then flagged 8 missing foreign-key indexes, 16 RLS policies re-evaluating `auth.uid()` per-row instead of once per query, and 10 "multiple permissive policy" overlaps on `roles`/`admin_permissions` (their "owner can do everything" policy and their "select own" policy both applied to `SELECT`, so both were evaluated on every read). Fixed by adding the missing indexes, wrapping every `auth.uid()` call in `(select auth.uid())` so Postgres evaluates it once via an initPlan, and splitting the two "for all" owner policies into insert/update/delete-only (since select was already fully covered by the dedicated select policy).
- First fix pass for the per-row re-evaluation issue only wrapped the *outer* function call (e.g. `(select private.is_owner(auth.uid()))`) on a handful of policies, not the inner `auth.uid()` itself — the linter's static check specifically wants the innermost `auth.<function>()` call wrapped (`private.is_owner((select auth.uid()))`). Caught by re-running the advisor after the first fix and seeing 9 findings remained; fixed with a targeted follow-up migration, after which both advisors returned a clean, empty result.

---

*(Next entry: continuing Phase 1 once Supabase service role key / JWT secret and Google OAuth credentials are provided.)*
