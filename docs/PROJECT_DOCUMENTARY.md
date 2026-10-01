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

### [2026-09-30] Phase 1 continued — Frontend Supabase wiring, auth pages, design system, dashboard shell

**Action**:
1. Committed all work from the previous entry as the first git commit (`bc45bc3`) after the user asked to commit before continuing. Root-commit had been created without the required `Co-Authored-By` attribution line on the first attempt; caught immediately and fixed with `git commit --amend` (safe since it was the unpushed root commit with nothing built on top of it yet).
2. Since the Supabase service role key, JWT secret, and Google OAuth credentials were still not provided, continued with everything in Phase 1 that doesn't depend on them: frontend Supabase wiring (using the already-available anon/publishable key), the design-system foundation, and the auth page UIs.
3. Installed frontend dependencies: `@supabase/supabase-js`, `@supabase/ssr`, `next-themes`, `framer-motion`, `zod`, `three`, `@react-three/fiber`, `@react-three/drei`, `zustand`.
4. Read the Next.js-generated `AGENTS.md` warning bundled in `apps/web` (auto-written by `next dev` on this Next.js 16.3.7/Turbopack install, warning that APIs may differ from training-data knowledge) and checked `node_modules/next/dist/docs/` before writing App Router code. Found a real breaking change: `middleware.ts` is deprecated in Next.js 16 and renamed to `proxy.ts` (same behavior, new file/export name) — used `proxy.ts` throughout instead of the older `middleware.ts` convention.
5. Wrote `lib/supabase/client.ts` (browser client) and `lib/supabase/server.ts` (server client, async `cookies()` per current Next.js API) using `@supabase/ssr`. Wrote `proxy.ts` at the project root to refresh the Supabase session cookie on every request.
6. Built the design-system foundation: rewrote `app/globals.css` with light/dark CSS variable tokens (background, foreground, card, primary, secondary, muted, accent, destructive, border, ring) and a Tailwind v4 `@custom-variant dark` (Tailwind v4 defaults to media-query dark mode; class-based toggling via `next-themes` needs this explicit variant). Wrapped the root layout in a `next-themes`-based `ThemeProvider` (`lib/theme/ThemeProvider.tsx`), added `suppressHydrationWarning` on `<html>` (required since next-themes sets the theme class client-side before hydration). Built `components/ui/ThemeToggle.tsx` with a `framer-motion`-animated switch.
7. Built the 3D loading-scene placeholder per the plan's Section 8.3: `components/three/scenes/RotatingIcosahedron.tsx` (a wireframe icosahedron rotating via `useFrame`), `components/three/LoadingScene.inner.tsx` (the actual `<Canvas>`, theme-aware color), and `components/three/LoadingScene.tsx` (the public export, `'use client'` + `next/dynamic(..., { ssr: false })` wrapper — required because `ssr: false` is only allowed from a Client Component in the App Router, not a Server Component).
8. Built minimal shared UI primitives (`components/ui/Button.tsx`, `Card.tsx`, `StubPage.tsx`, `SignOutButton.tsx`) used across every page from here on.
9. Built the authentication flow from `docs/IMPLEMENTATION.md` Section 7: `app/(auth)/sign-in/page.tsx` ("Continue with Google" primary action, with a toggle-able email+password fallback form since a password becomes a valid alternate login method after account setup); `app/auth/callback/route.ts` (OAuth code exchange, then branches to `/account-setup` or `/dashboard` depending on whether a `profiles` row already exists); `app/(auth)/account-setup/page.tsx` + `AccountSetupForm.tsx` (Server Component gate + Client Component form: shows the Google-provided Gmail address read-only, takes a new password with `zod`-less inline validation, calls `supabase.auth.updateUser({ password })` then inserts the `profiles` row).
10. Realized the account-setup flow had a real architectural gap: after creating the `profiles` row, the client would also need to insert into `roles` to implement "first user becomes Owner" -- but the RLS policy on `roles` requires an existing Owner to write to that table at all, so a brand-new user could never insert their own role row client-side. Solved by moving that logic into the database itself: applied a new migration (`0010_auto_assign_role_on_profile_creation.sql`) adding a `SECURITY DEFINER` trigger function (`private.handle_new_profile`) that fires after every `profiles` insert and assigns `owner` if no owner exists yet, otherwise `user` -- bypassing the client-side RLS problem entirely since the trigger runs with elevated privileges.
11. Built `lib/auth/guards.ts` (`requireUser`, `requireRole`) implementing the "must have a `profiles` row" redirect rule from the plan's Section 7.3.
12. Built the dashboard shell: `app/(dashboard)/layout.tsx` (sidebar nav gated by role -- Team/Question Bank links only shown to Owner -- topbar with email, theme toggle, sign-out) and stub pages for every section (`dashboard`, `chat`, `interviews`, `interviews/setup` -- this one previews the real `LoadingScene` component -- `ats-score`, `resumes`, `reports`, `settings/api-keys`, `settings/team`, `admin/question-bank`), each wrapped in the `requireUser`/`requireRole` guard as appropriate.
13. Replaced the default Next.js starter `app/page.tsx` with a root-route redirect: signed-in users go to `/dashboard`, everyone else to `/sign-in`.
14. Verified everything: `npx tsc --noEmit` clean (no type errors); booted the dev server via the browser-preview tool and confirmed in the actual browser that `/` redirects to `/sign-in`, the sign-in page renders correctly, the theme toggle smoothly switches light/dark (screenshotted both), the email/password fallback form renders, and navigating to the auth-gated `/interviews/setup` correctly redirects an unauthenticated visitor back to `/sign-in`. No console errors in any of these checks.
15. Kicked off `npx eslint .` to lint the whole frontend before the next commit (running in background at the time of this entry).

**Why**: Continuing Phase 1 (`docs/IMPLEMENTATION.md` Section 9, Phase 1) as far as possible without the still-missing Supabase service role key/JWT secret and Google OAuth credentials, which block only the final live-auth wiring and the FastAPI-side JWT verification test.

**Result**: The full frontend auth flow, design-system foundation, and dashboard shell are built, type-check cleanly, and were manually verified in a real browser (both themes, redirects, forms). The Google sign-in button itself cannot be end-to-end tested yet since no Google OAuth provider is configured in Supabase.

**Problems faced**:
- First git commit was missing the required commit-attribution line; fixed via amend since it was the unpushed root commit (see action #1).
- Next.js 16 deprecated `middleware.ts` in favor of `proxy.ts` -- would have silently built on the wrong convention if the bundled `AGENTS.md`/docs warning hadn't been checked first.
- Tailwind v4 defaults to `prefers-color-scheme`-based dark mode, which is incompatible with `next-themes`' class-based toggling; needed an explicit `@custom-variant dark (&:where(.dark, .dark *));` in `globals.css` to make `dark:` utilities respond to the `.dark` class next-themes sets instead.
- three.js `Color` cannot parse CSS custom properties (`var(--color-primary)`) directly -- had to resolve the theme's primary color to a literal hex string in `LoadingScene.inner.tsx` (via `useTheme()`) and pass it down as a prop, rather than referencing the CSS variable directly in the material.
- Realized mid-build that the account-setup flow could not correctly implement "first user becomes Owner" purely in client code, because of the same RLS chicken-and-egg problem described in action #10 -- caught before shipping broken signup, fixed with a DB trigger instead of client-side role insertion.

---

**ESLint follow-up**: the background ESLint run from step 15 came back with 1 error and 3 warnings, all fixed before committing:
- `components/ui/ThemeToggle.tsx` had a hard error ("Calling setState synchronously within an effect can trigger cascading renders") on the standard `useEffect(() => setMounted(true), [])` hydration-guard pattern -- the project's `eslint-plugin-react-hooks` version flags this as an anti-pattern even though it's the common `next-themes` idiom. Replaced it with `useSyncExternalStore` (server snapshot `false`, client snapshot `true`), which is the React-recommended primitive for exactly this "has this mounted on the client yet" check and doesn't trigger the rule.
- Three files (`sign-in/page.tsx`, `AccountSetupForm.tsx`, `SignOutButton.tsx`) used `window.location.href` for internal navigation, flagged by `@next/next/no-location-assign-relative-destination`. Replaced all three with `useRouter().push()` + `router.refresh()` (the refresh ensures the Server Component dashboard layout re-runs `requireUser()` against the now-current session instead of serving a stale redirect).
- Re-ran both `npx tsc --noEmit` (clean) and `npx eslint .` (clean, exit code 0) after the fixes, then re-verified the sign-in page and theme toggle live in the browser again (both themes, no console errors) before committing.

Committed as `849af98`.

---

### [2026-10-01] Phase 2 — BYOK system: provider adapters, key encryption/failover, onboarding UI

**Action**:
1. User confirmed the three pending credentials (Supabase service role key/JWT secret, Google OAuth, Cloudflare R2) will be provided whenever convenient, and approved continuing with everything in Phase 2 that doesn't require them.
2. Added a `notifications` table migration (`0011_notifications.sql`) to back the "notify user after key failover" requirement from the BYOK design -- owner-only select/update via RLS, insert/delete reserved for the backend's service-role client. Verified clean on the security advisor immediately after applying.
3. Built `app/providers/base.py`: the shared `ProviderAdapter` interface (`validate`, `chat`, `embed`) plus `ProviderRateLimitError`/`ProviderAuthError` exception types used uniformly across all three provider modules so orchestration code never branches on provider identity.
4. Built the three provider adapters:
   - `gemini.py` -- uses `generate_content_async` (native async in this SDK version) for chat/validate, `asyncio.to_thread` to wrap the sync-only `embed_content` call, maps `ResourceExhausted` -> `ProviderRateLimitError` and `PermissionDenied`/`Unauthenticated` -> auth failure.
   - `claude.py` -- uses `AsyncAnthropic`, `messages.stream()` for streaming chat, maps `RateLimitError`/`AuthenticationError`. No `embed()` override (Claude has no embeddings API).
   - `groq.py` -- uses `AsyncGroq` (OpenAI-compatible chat completions, async streaming natively), same rate-limit/auth mapping. No `embed()` override (Groq has no embeddings API either).
5. Built `app/providers/registry.py` (provider name -> adapter instance lookup).
6. Built `app/keys/service.py`: `submit_key` (encrypt via the Fernet helper from Phase 1's `core/security.py`, upsert into `provider_keys`, immediately call the adapter's `validate()`, store the result), `list_keys`, `delete_key`, and `call_with_failover` -- the primary/backup retry helper from the plan's Section 6.3, explicitly scoped to one-shot async calls (validate/embed/non-streaming chat). Documented inline why streaming chat failover is a different problem (can't simply "retry" after partially yielded output) and is deferred to the chat/interview services that will actually consume streaming responses in later phases.
7. Built `app/keys/router.py` (`POST /keys`, `GET /keys`, `DELETE /keys/{id}`) and wired it into `main.py`. Initially added a fourth endpoint (`GET /keys/gemini/status`) for the onboarding gate, then removed it as redundant -- the frontend can just call `GET /keys` and check client-side, and the onboarding gate itself ended up living in Next.js directly against Supabase (see step 10) rather than needing a dedicated FastAPI endpoint at all.
8. Wrote `tests/test_keys.py`: 5 unit tests covering `call_with_failover` -- success on primary, fail-over to backup with a forced `ProviderRateLimitError` (and confirms the notification fires with the right message), both-keys-exhausted, no-backup-configured, and no-primary-key-configured. All mock `_get_key_row`/`_notify`/`decrypt_key` directly rather than hitting a real Supabase connection, so they run fully offline. All 5 passed; fixed one pytest-asyncio deprecation warning by setting `asyncio_default_fixture_loop_scope = function` in `pytest.ini`.
9. Built the frontend key-management UI: `lib/api-client/fastapi.ts` (forwards the Supabase session's JWT as `Authorization: Bearer` to FastAPI), `types/keys.ts` (provider metadata: label, "how to get this key" instructions, and a direct link, for Gemini/Claude/Groq), `components/settings/ProviderKeyForm.tsx` (single provider+slot key entry with live validation feedback), `components/settings/ProviderKeySection.tsx` (wraps primary+backup forms for one provider, expandable backup-key section).
10. Built `app/(auth)/onboarding/page.tsx` + `OnboardingFlow.tsx`: a 2-step flow (mandatory Gemini key, gated "Continue" button; then optional Groq/Claude) reusing the same `ProviderKeySection` component. Built the real `settings/api-keys/page.tsx` (replacing Phase 1's stub) reusing the identical components. Extended `lib/auth/guards.ts::requireUser` to also check for a valid primary Gemini key via a direct RLS-protected Supabase query (no FastAPI round-trip needed, since this is simple ownership-scoped CRUD, not an LLM-touching operation) and redirect to `/onboarding` if missing -- since the dashboard layout already calls `requireUser`, this one change gates every dashboard route. Changed `AccountSetupForm`'s post-setup redirect from `/dashboard` to `/onboarding` directly (a brand-new user has no keys yet, so landing on `/dashboard` first would just immediately bounce them to `/onboarding` anyway via the guard -- went straight there instead).
11. Verified: `npx tsc --noEmit` clean; FastAPI app imports cleanly with all routes registered (`/keys`, `/keys/{key_id}`, plus the existing health routes); booted the dev server and confirmed both `/onboarding` and `/settings/api-keys` correctly redirect an unauthenticated visitor to `/sign-in` (proving the new Server Component gates don't crash) with zero console errors.

**Why**: Continuing Phase 2 (`docs/IMPLEMENTATION.md` Section 9) as far as possible without live Supabase/Google credentials -- everything here is either pure code, unit-testable via mocks, or verifiable through the "does it redirect correctly / does it compile" level of browser testing that doesn't require a real signed-in session.

**Result**: The full BYOK backend (provider adapters, encryption, validation, failover) and frontend (onboarding flow, key management UI, the Gemini-required dashboard gate) are built, tested where testable offline, and verified not to crash. What's still unverified: an actual live key submission round-trip (needs a running FastAPI instance with real Supabase credentials) and the real provider API calls themselves (needs real BYOK keys from each provider, which is naturally a user-side step regardless of blocked credentials).

**Problems faced**:
- None blocking -- the main judgment call was recognizing that `GET /keys/gemini/status` was an unnecessary FastAPI endpoint once it became clear the onboarding gate's "does a valid key exist" check is simple RLS-protected CRUD and belongs in Next.js directly per the plan's own architecture principle (FastAPI only for LLM-touching/RAG/voice work), not a reason to round-trip through FastAPI.

---

Committed as `5020b79`.

---

### [2026-10-01] Temporary demo sign-up (email/password) -- explicitly flagged for removal

**Action**: At the user's request, added a temporary email/password account-creation page so the team can demo the product and test end-to-end before Google OAuth credentials are configured, since that was the one piece blocking any real sign-up at all. Built `app/(auth)/sign-up/page.tsx`, opening with a prominent comment block stating it's temporary dev/demo scaffolding to be deleted once Google sign-in is live and verified, per `docs/IMPLEMENTATION.md` Section 7 (Google-only is still the locked target end-state, this is a dev-only exception, not a plan change). Linked it from `sign-in/page.tsx` as "Create a demo account (dev only)", also clearly marked. The flow: `supabase.auth.signUp()` -> if a session comes back immediately (email confirmation disabled on the project), create the `profiles` row right away (same DB trigger assigns the role) and go straight to `/onboarding` since the password is already set at signup, no separate "set password" step needed; if no session comes back (confirmation required), show a "check your email" message instead.

**Why**: Explicit user request -- unblocks real end-to-end testing of everything built so far (auth guards, onboarding gate, dashboard, BYOK key entry) without waiting on Google Cloud Console setup, while keeping the final auth model unchanged and the temporary piece impossible to miss when it's time to remove it.

**Result**: `npx tsc --noEmit` and `npx eslint .` both clean. Live-tested in the browser:
- Submitting an invalid-format email (`.test` TLD) correctly showed Supabase's own inline validation error.
- Submitting a reserved/non-deliverable domain (`example.com`) was also correctly rejected by Supabase (RFC 2606 domains are apparently denylisted for signup), with the error surfaced inline exactly as expected.
- Submitting a syntactically valid Gmail-style address got past validation and attempted to actually send a confirmation email, at which point Supabase returned "email rate limit exceeded" -- the free tier's built-in email sending has a very low hourly cap, and my own repeated test attempts in this session exhausted it.

This confirms two things: the sign-up code itself is wired correctly end-to-end (validation errors, and the actual auth request reaching Supabase's mail-sending step), and the project currently has **email confirmation enabled**, which combined with the low rate limit will make demo account creation slow/frustrating in its current config.

**Problems faced**:
- Couldn't complete a full successful demo signup in this session because of the combination of (a) email confirmation being on and (b) the free-tier email rate limit being exhausted by the test attempts themselves. This isn't a code bug -- it's a Supabase project *setting* (Authentication -> Providers -> Email -> "Confirm email" toggle) that only the user can change from the dashboard; no MCP tool is available to toggle Supabase Auth settings programmatically. Flagged to the user: disabling email confirmation would make demo signups instant and avoid the rate limit entirely, recommended but left as their choice since it's a project-level security setting.

---

### [2026-10-01] File-naming cleanup -- every route now page.tsx + a named view component

**Action**: The user flagged (referencing an earlier stated preference) that routes shouldn't just be generically-named `page.tsx` files. Clarified first that Next.js App Router hard-requires the literal filename `page.tsx`/`layout.tsx` for its file-based routing to find a route at all -- that part can't change. What *can* change is keeping that file as a one-line re-export and putting all actual content in a clearly-named sibling component. Confirmed the approach with the user (apply it everywhere, including the simple stubs, not just pages with real logic), then refactored all 13 routes that had inline content: `sign-in` -> `SignInView.tsx`, `sign-up` -> `DemoSignUpView.tsx`, the `(dashboard)` layout -> `DashboardShell.tsx`, and each dashboard page (`dashboard`, `chat`, `interviews`, `interviews/setup`, `ats-score`, `resumes`, `reports`, `settings/api-keys`, `settings/team`, `admin/question-bank`) -> its own `XView.tsx`. `account-setup` and `onboarding` were left untouched since they already followed the right shape (a clearly-named async function doing real redirect/data-fetch work, delegating UI to a named component) -- not every `page.tsx` needs to be a trivial re-export, only ones that were acting as an unnamed dumping ground for view logic. Root `app/layout.tsx` and `app/page.tsx` were also left as-is: minimal framework bootstrap (fonts, metadata, a bare auth-redirect) with no "view" content worth extracting.

**Why**: Direct user request, tracing back to an original stated preference for a decent, clearly-named folder/file structure rather than a pile of ambiguous `page.tsx` files.

**Result**: `npx tsc --noEmit` and `npx eslint .` both clean. Booted the dev server and confirmed `/` still redirects correctly, `/sign-in` renders pixel-identical to before the refactor, `/sign-up` loads with no console errors -- confirming the re-export pattern (`export { X as default } from "./X"`) didn't change any runtime behavior. Committed as `b7018a4`.

**Problems faced**: None -- mechanical refactor, no logic changes, each file verified to compile immediately after creation.

---

### [2026-10-01] Theme toggle redesign

**Action**: Per user request, replaced the sliding pill/track theme toggle with a simple circular icon button (no track), using hand-drawn SVG sun/moon glyphs (no emoji) and a rotate/fade crossfade transition on click, after confirming via a clarifying question that "different control type" (not just different icons, or repositioning) was wanted.

**Why**: Direct user request.

**Result**: `npx tsc --noEmit` and `npx eslint .` clean. Verified live in the browser: renders as a clean circular button, click correctly crossfades between sun/moon and switches the whole page's theme, hover state shows the accent background. Committed as `0751659`.

---

### [2026-10-01] Phase 3 -- AI Chatbot service

**Action**:
1. Added the `conversations` + `chat_messages` tables (migration, applied to the live Supabase project and saved locally as `0012_chat.sql`) -- `chat_messages` deliberately named (not just `messages`) to stay unambiguous as more tables get added later. RLS: conversation ownership gates both tables (messages scoped via a join to their parent conversation, same pattern as `interview_transcripts`). Security and performance advisors both clean immediately after applying.
2. While wiring the new `chat/service.py`, noticed it needed to import `_get_key_row`/`_notify` from `keys/service.py` -- both underscore-prefixed "private" helpers. Rather than reach across a module boundary for private names, renamed them to public `get_key_row`/`notify_user` in `keys/service.py` (its own docstring had already anticipated this exact cross-module reuse) and updated `call_with_failover` and `tests/test_keys.py` to match. All 5 existing key tests still passed after the rename.
3. Built `chat/service.py`: `create_conversation`, `list_conversations`, `list_messages` (with an ownership check via `_require_owned_conversation`), and `stream_reply` -- the streaming failover generator described in Section 7's design-time limitation: tries the primary key, and only retries with the backup key if the rate-limit error occurs *before any chunk has been yielded* (once output has started, a partial response can't be safely discarded and retried); notifies the user on a successful fallback, same as the one-shot `call_with_failover` path. Raises a 412 if no key is configured at all, 429 if rate-limited with no backup available.
4. Built `chat/router.py`: `POST/GET /chat/conversations`, `GET /chat/conversations/{id}/messages`, and `POST /chat/conversations/{id}/messages` returning a `StreamingResponse` (plain chunked text) wrapping `stream_reply`. Wired into `main.py`.
5. Wrote `tests/test_chat.py`: 4 tests using a `FakeAdapter` test double (an async generator yielding canned chunks, configurable to raise `ProviderRateLimitError` before any chunk) -- covers the full-success path, the before-any-chunk failover path (and that the notification fires), the no-key-at-all 412, and the rate-limited-with-no-backup 429. All passed, run alongside the existing 5 key tests (9/9 total).
6. Frontend: `types/chat.ts`; added `apiClient.streamPost` to `lib/api-client/fastapi.ts` (reads the fetch response body via `getReader()`/`TextDecoder`, yielding decoded chunks -- chosen over `EventSource`/SSE specifically because `EventSource` can't send the `Authorization` header this app's auth model requires); `components/chat/MessageBubble.tsx` and `ChatWindow.tsx` (provider selector restricted to providers with a valid key, optimistic local message append, live-appends streamed chunks to the in-progress assistant bubble); `chat/ChatListView.tsx` (conversation list + "New chat") and `chat/[conversationId]/ChatThreadView.tsx` (fetches message history + valid-provider list, renders `ChatWindow`) -- both following the page.tsx-is-a-thin-wrapper convention from the earlier file-naming cleanup. The dynamic route's `page.tsx` is a small async Server Component that awaits the `params` promise (confirmed via the bundled Next.js 16 docs that `params` is always a promise now, must be awaited or read via `use()`) and passes the resolved id down as a prop -- the same "legitimate routing-boundary logic" exception as `account-setup`/`onboarding`.
7. Verified: `npx tsc --noEmit` and `npx eslint .` both clean. FastAPI app imports with all `/chat/*` routes registered. Booted the FastAPI server for real (even without live Supabase credentials) and confirmed with `curl` that `/health` returns 200, a request to `/chat/conversations` with no token returns a clean 401 "Missing bearer token", and with a bogus token returns a clean 401 "Invalid or expired token" -- proving the auth dependency itself works correctly independent of the still-missing Supabase service role key/JWT secret. Booted the frontend dev server and confirmed `/chat` and `/chat/<id>` both correctly redirect an unauthenticated visitor to `/sign-in` with no console errors.

**Why**: Continuing the agreed build order (`docs/IMPLEMENTATION.md` Phase 3) -- the Chatbot service is deliberately first among the three products specifically to validate the provider-adapter/key-failover plumbing end-to-end before the harder two services (Interviewing Agent, ATS Score) are built on top of it.

**Result**: The full chat backend (conversations, streaming replies, failover) and frontend (list + thread UI, streaming render) are built and unit-tested. What remains unverified is the actual live round-trip -- a real signed-in user picking a real provider and getting a real streamed reply -- which needs both the Supabase service role key/JWT secret (to run the backend against real auth) and a real BYOK provider key. Per Phase 3's definition of done, this is the next thing to confirm once those are available.

**Problems faced**: None blocking. The one real design decision was recognizing the underscore-prefixed `keys/service.py` helpers needed to become a proper public cross-module API rather than being imported by their "private" names from `chat/service.py` -- fixed immediately, before it became a pattern repeated into future phases.

---

### [2026-10-01] Phase 4 -- RAG foundation (parsing, chunking, embedding, retrieval)

**Action**:
1. **Real schema correction found during implementation**: the original plan gave each resume a single `embedding` column, but real RAG retrieval needs to match a specific JD requirement against the specific relevant *section* of a resume, not the whole document as one vector -- a single embedding per resume can't support that. Added a `resume_chunks` table (one row per chunk, its own embedding) and dropped the now-superseded `resumes.embedding` column. Also renamed `resumes.file_url` to `file_key` before any real data existed, since it was always going to hold an R2 object key, not a real browsable URL (the bucket is private). Updated `docs/IMPLEMENTATION.md` Section 5 and the Phase 4 plan text to match -- unlike the temporary demo sign-up, this is a genuine correction meant to stand as the new reality going forward, not a tracked deviation.
2. Added two pgvector cosine-similarity RPC functions (`match_resume_chunks`, `match_question_bank`), callable via Supabase's `.rpc()`. Kept them as plain SQL functions (not `SECURITY DEFINER`) since they're meant to be legitimately callable, not internal auth-bypass helpers like `private.is_owner` -- RLS on the underlying tables still applies normally if ever called directly by a non-service-role client. Set `search_path` explicitly on both regardless, consistent with the Phase 1 hardening pattern. Both advisors clean immediately after applying.
3. Built the backend RAG pipeline: `rag/parsing/{pdf,docx}.py` + a dispatch `__init__.py` (extension-based); `rag/chunking.py` (section-aware splitting on common resume headings -- Experience, Education, Skills, etc. -- falling back to fixed-size windows with overlap for anything too long or unstructured to split that way); `rag/embeddings.py` (always routes through the Gemini adapter regardless of the user's chat-provider choice, concurrent via `asyncio.gather` for multi-chunk batches); `rag/retrieval.py` (thin wrappers around the two new RPCs).
4. Built `core/storage.py` -- R2 download only. Confirmed the actual upload responsibility belongs in Next.js per the architecture principle (simple storage CRUD is not an LLM/RAG concern), so FastAPI's only storage job is fetching a file back by its key to parse it.
5. Built `rag/service.py::process_resume` -- fetches the owned resume row, requires a valid primary Gemini key (412 if missing), downloads from R2, extracts text, chunks it (422 if nothing extractable), embeds every chunk, then atomically replaces that resume's `resume_chunks` and updates `parsed_text`. Wired into `rag/router.py` as `POST /rag/resumes/{id}/process` and into `main.py`.
6. Wrote 13 new backend tests: `test_chunking.py` (5, pure logic -- empty input, short text, heading-based splitting, long-text fallback windowing both with and without headings), `test_parsing.py` (4, including a real DOCX round-trip built with `python-docx` itself rather than a fixture file, plus extension-dispatch and unsupported-type error cases), `test_rag_service.py` (4, `process_resume`'s full orchestration with every external call -- Supabase, R2, Gemini -- mocked out: success path, missing-key 412, no-chunks 422, not-owned 404). All 22 backend tests passing (9 from before + 13 new).
7. Frontend: installed `@aws-sdk/client-s3` and `server-only`; built `lib/storage.ts` (`uploadToR2`/`deleteFromR2`, guarded with `import "server-only"` so it can never accidentally end up in a client bundle); `app/api/resumes/route.ts` (POST: validates extension/size, uploads to R2, inserts the `resumes` row, then calls the FastAPI processing endpoint -- a processing failure doesn't fail the upload itself, since the file is already safely stored; GET: lists the signed-in user's resumes) and `app/api/resumes/[id]/route.ts` (DELETE: removes both the DB row and the R2 object); rewrote `resumes/ResumesView.tsx` with a real upload button, a processed/pending status per resume, and delete.
8. Verified everything not gated on live R2/Gemini credentials: `npx tsc --noEmit` and `npx eslint .` both clean; booted FastAPI for real and confirmed with `curl` that `POST /rag/resumes/{id}/process` cleanly 401s on a missing or bogus token before ever touching R2/Supabase; booted the frontend and confirmed `/resumes` redirects an unauthenticated visitor to `/sign-in` with no console errors.

**Why**: Continuing the agreed build order (`docs/IMPLEMENTATION.md` Phase 4) -- this pipeline is shared infrastructure both the Interviewing Agent (Phase 6+) and ATS Score (Phase 5) depend on, which is exactly why it's built before either of them.

**Result**: The full parsing -> chunking -> embedding -> storage pipeline and the resume upload/management UI are built and unit-tested (22/22 backend tests passing). What remains unverified is the real end-to-end path -- an actual PDF/DOCX uploaded to a real R2 bucket, downloaded back, parsed, and embedded with a real Gemini key -- which needs the Cloudflare R2 credentials (still not provided) plus the Supabase service role key/JWT secret and a real Gemini key.

**Problems faced**: None blocking. The one substantive judgment call was the `resume_chunks` schema correction (point 1) -- caught early, before any real resume data existed, by thinking through what the retrieval step would actually need to query against rather than only following the original plan's schema literally.

---

### [2026-10-01] Phase 5 -- AI Resume ATS Score service

**Action**:
1. Built `ats/llm_utils.py::complete_text` -- a one-shot (non-streaming) LLM call wrapped in `call_with_failover`, shared by requirement extraction and feedback generation (both are single request/response calls, unlike chat's streaming replies, so they fit `call_with_failover`'s one-shot shape directly rather than needing chat's special partial-output-aware failover logic).
2. Built `ats/requirements_extractor.py`: prompts the model to return strict JSON (`must_have`, `nice_to_have`, `experience_level`, `title`) from the JD text, with a `_extract_json` helper that strips markdown code fences and falls back to regex-extracting the first `{...}` block, since LLMs don't always obey "no markdown" instructions perfectly.
3. Built `ats/scorer.py` -- pure, LLM-free logic: `keyword_score` (must-have terms weighted double a nice-to-have, exact + a small curated synonym map for common abbreviations like JS/JavaScript, ML/machine learning, K8s/Kubernetes), `formatting_score` (a heuristic proxy for "would a real ATS parse this cleanly" -- checks for an email, a phone number, a standard section heading, and average line length, since badly-extracted multi-column PDFs tend to produce lots of short fragment lines), `missing_terms` (for the feedback step), and `composite_score` (the plan's 40/40/20 weighting).
4. Built `ats/feedback.py` -- turns the raw scores and missing-keyword lists into a short, actionable bullet-point LLM response rather than restating the numbers back to the user.
5. Built `ats/service.py::score_resume` orchestrating all of the above: requires the resume to exist and be processed already (404 / 422), requires a valid Gemini key for the semantic-similarity step (412, since embeddings always route through Gemini regardless of which provider the user picked for the reasoning calls), computes semantic score by embedding each requirement term individually and taking its best match against that resume's `resume_chunks` via the Phase 4 retrieval RPC, then composes everything into one response. Both LLM-calling steps (extraction, feedback) can independently exhaust both keys, each mapped to a 429.
6. Wired `ats/router.py` (`POST /ats/score`, no persistence per the plan's explicit decision) into `main.py`.
7. Wrote 19 new backend tests: `test_scorer.py` (9, pure logic -- full/partial/synonym keyword matching, missing-terms reporting, formatting heuristics including the empty-text edge case, composite weighting), `test_requirements_extractor.py` (5, JSON extraction from plain/fenced/commentary-wrapped responses, the no-JSON-found error case, and default-filling for a response missing optional fields), `test_ats_service.py` (5, the full orchestration with Supabase/Gemini/embeddings/LLM calls all mocked -- success path, 404, 412, and both independent 429 paths). All 41 backend tests passing (22 from before + 19 new).
8. Frontend: `types/ats.ts`; `components/ats/ScoreBreakdown.tsx` (composite score, three animated sub-score bars color-coded by threshold, missing-keywords list, written feedback -- deliberately a plain function component with no `"use client"` of its own, since it only ever renders transitively inside the already-client `AtsScoreView`, the same pattern already used by `MessageBubble.tsx`); rewrote `ats-score/AtsScoreView.tsx` (replacing Phase 1's stub) with a resume selector restricted to already-processed resumes, a provider selector restricted to valid keys, a JD textarea, and the score breakdown rendered on completion.
9. Verified everything not gated on live credentials: `npx tsc --noEmit` and `npx eslint .` both clean; booted FastAPI for real and confirmed with `curl` that `POST /ats/score` cleanly 401s on a missing or bogus token; booted the frontend and confirmed `/ats-score` redirects an unauthenticated visitor to `/sign-in` with no real console errors (only the same known-benign HMR-reconnect noise from this long dev session, already seen and dismissed in earlier phases).

**Why**: Continuing the agreed build order (`docs/IMPLEMENTATION.md` Phase 5) -- directly follows Phase 4 since this service is the RAG foundation's first real consumer.

**Result**: The full ATS scoring pipeline (requirement extraction, three independent sub-scores, composite, written feedback) and its UI are built and unit-tested (41/41 backend tests passing). What remains unverified is the real end-to-end path -- an actual processed resume scored against a real JD using real provider keys -- which needs the same still-missing credentials as every other phase so far (Supabase service role key/JWT secret, Cloudflare R2, and at least one real BYOK key).

**Problems faced**: None blocking. No new architectural surprises this phase -- it built cleanly on the Phase 2 (BYOK/failover) and Phase 4 (RAG/retrieval) foundations exactly as the plan anticipated.

---

*(Next entry: live end-to-end testing of the full signup -> onboarding -> chat -> resume-upload -> ATS-score round-trip once Supabase service role key / JWT secret / Google OAuth / Cloudflare R2 credentials are provided.)*
