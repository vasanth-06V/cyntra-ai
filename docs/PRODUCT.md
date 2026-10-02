# CyntraAI — Complete Product Document (A to Z)

> Snapshot date: **2026-10-02** · Repo: `C:\Study\Project4-Cyntra AI\Cyntra_AI` · Branch `main` · 31 commits
> This is the single "everything about the product" document. Companion files: `docs/IMPLEMENTATION.md` (original fixed plan), `docs/PROJECT_DOCUMENTARY.md` (chronological build journal with problems faced), `docs/PILLARS_PLAN.md` (proposed next plan: RAG / LLM / backend pillars).

**Status legend:** ✅ Built and automated-tested · 🟡 Built, **not yet verified live** (mock-tested only) · 🔜 Planned / upcoming · ⏸ Deferred on purpose · ❌ Declined (will not build)

---

## 1. What CyntraAI is

A **single-tenant AI platform** with three services under one account system, run on a **BYOK (Bring Your Own Key)** model — users supply their own LLM API keys, so the platform pays nothing for LLM usage and the infrastructure targets **$0/month**.

| Service | One-line description | Status |
|---|---|---|
| **AI Chatbot** | Chat with any provider you have a valid key for (Gemini / Claude / Groq), streamed | ✅ built, verified live with Gemini |
| **AI Interviewing Agent** | Timed 1-hour mock interviews in 8 types, personalized from your resume + a job description; later with a coding editor and voice | 🟡 text mode built; coding platform, voice, reports 🔜 |
| **AI Resume ATS Score** | Scores a resume against a JD like a real ATS (keyword + semantic + formatting + written feedback) | 🟡 built, needs R2 to run live |

**Roles:** *Owner* (first user ever; full control) · *Admin* (permissions individually granted by the Owner, e.g. `manage_question_bank`) · *Application User*.

---

## 2. Feature catalog

### 2.1 Accounts, auth and roles
| Feature | Status |
|---|---|
| Google sign-in (Supabase Auth, OAuth) | ✅ verified live |
| Account-setup step (Gmail shown read-only + set a password used as an *alternate login*) | ✅ |
| Profile + role created automatically; **first user becomes Owner** (DB trigger) | ✅ (race-safe, applied via migration 0019) |
| Route guards (signed in → account setup → onboarding → dashboard), role/permission helpers (`requireRole`, `requirePermission`) | ✅ |
| Backend JWT verification (ES256 via JWKS, HS256 fallback, `exp` required, blank-secret refused) | ✅ |
| Temporary demo email/password sign-up page (for building without Google) | ✅ exists — **must be deleted before launch** |
| Team management page (Owner promotes/demotes admins, grants permissions) | 🔜 stub page only |

### 2.2 BYOK key system
| Feature | Status |
|---|---|
| Providers: Gemini, Claude, Groq; **primary + backup slot** each | ✅ |
| Gemini key **mandatory** (only embeddings provider); Claude/Groq optional | ✅ |
| Keys encrypted at rest (Fernet); never returned to the client | ✅ |
| Server-side validation before storing (Gemini: list-models, no quota; Claude/Groq: 1 tiny call); bad keys are never stored | ✅ |
| Guided onboarding with per-provider "how to get your key" instructions; Settings → API Keys management | ✅ |
| Automatic silent failover primary → backup on rate limit, then a notification | ✅ (notifications are written; nothing displays them yet 🔜) |
| Delete a key from the UI | 🔜 (API exists) |
| "Used today" usage line (requests / tokens per provider) | ✅ |

### 2.3 AI Chatbot
| Feature | Status |
|---|---|
| Conversations list, thread, streamed replies, provider selector (only providers with valid keys) | ✅ |
| History window (last 10 messages, ≤2,000 tokens) | ✅ |
| Friendly errors (no key, quota, overloaded, blocked reply) | ✅ |
| Rename/delete conversation, titles | 🔜 |

### 2.4 Resumes and RAG (shared by ATS and Interviews)
| Feature | Status |
|---|---|
| Upload PDF/DOCX (≤5 MB, type + signature check) to private Cloudflare R2 | 🟡 code done; **R2 credentials not yet configured** |
| Parse (pdfplumber / python-docx) → section-aware chunking → one batched Gemini embedding → pgvector storage | 🟡 |
| One-time resume digest (~300 tokens) reused by interviews | 🟡 |
| Retry processing button; delete (with clear message if used by an interview) | ✅ |
| Question bank retrieval (cosine similarity against the JD) | 🟡 |

### 2.5 ATS Resume Score
| Feature | Status |
|---|---|
| JD → structured requirements (LLM, JSON mode, cached per user+JD for 1 h) | 🟡 |
| Keyword score (whole-word, synonyms), semantic score (embeddings), formatting score (heuristics) → weighted composite 0–100 (40/40/20), **all sub-scores shown** | 🟡 |
| Written actionable feedback (LLM) | 🟡 |
| **No history stored** (decision) | ✅ by design |
| Calibrated semantic scoring, evidence per requirement | 🔜 (RAG v2) |

### 2.6 Interviewing Agent
| Feature | Status |
|---|---|
| 8 interview types: **Coding, Behavioral, HR, ML/AI, Web Dev, SDE, System Design, Case Study**, each with its own phase list and time split (always 60 min total) | ✅ |
| Setup: pick a resume + paste a fresh JD; one structured call produces a brief + personalized opening | 🟡 |
| Orchestrator: phases advance by elapsed time; interview auto-completes after time + 5 min grace | ✅ |
| Token-lean turns: brief + phase goal + running summary + last turns, ≤1,200-token prompt, ≤160-token reply | ✅ |
| Incremental running summary (every 8 new turns) | ✅ |
| Interview providers: **Gemini + Groq only** (Claude excluded — no native audio) | ✅ |
| Interview room UI (transcript, phase/timer, send answer, end interview) | 🟡 |
| Question bank admin (Owner/Admins with permission): create/edit/delete with test cases and tags, embedded on save | 🟡 |
| Polished ~5-minute "setting up" screen with progress messages and 3D scene | 🔜 (currently synchronous + static scene) |
| **Coding platform** (Monaco editor + Judge0 test-case execution, 2 RAG-selected questions) | 🔜 Phase 7 |
| **Voice** (AI speaks via TTS, live STT transcript, silence/interruption handling) — "the heart of the product" | 🔜 Phase 8 |
| **Post-interview report**, downloadable for exactly 7 days then purged | 🔜 Phase 9 |
| Untimed practice mode | ⏸ deferred |
| Session recording/playback | ❌ declined |
| Anti-cheat (tab-switch monitoring) | ⏸ deferred |

### 2.7 UI/UX
| Feature | Status |
|---|---|
| Light + dark themes with tokens, icon theme toggle | ✅ |
| framer-motion transitions; 3D loading scene (three.js) used only for setup/loading moments | ✅ basic · 🔜 final polish (Phase 10) |
| Dashboard shell with sidebar (+ mobile nav bar) | ✅ |
| Accessibility pass, reduced motion, error-state sweep | 🔜 Phase 10 |

---

## 3. Architecture and tech stack

```
Browser ── Next.js 16 (Vercel) ──────────────► Supabase (Postgres + pgvector + Auth)
   │          • auth/session (proxy.ts)         ▲
   │          • resume upload/list/delete       │ service-role (backend) / RLS (browser reads)
   │            route handlers ───► Cloudflare R2 (private bucket: resumes, later reports)
   └─ Bearer JWT ─► FastAPI (Render) ───────────┘
                     • core: security (JWT, Fernet), config, db, storage
                     • llm: gateway → limiter → provider adapters (Gemini / Claude / Groq)
                     • keys, chat, rag, ats, interviews (+ question bank), usage
                     • (planned) coding (Judge0), voice, reports, jobs
```

| Layer | Choice |
|---|---|
| Frontend | Next.js 16.3 (TypeScript, App Router, Turbopack), Tailwind v4, next-themes, framer-motion, three/@react-three, `@supabase/ssr` |
| Backend | Python 3.13, FastAPI, pydantic, supabase-py (sync client in threads), boto3 (R2), cryptography, pdfplumber, python-docx; SDKs: `google-generativeai` 0.8.3, `anthropic`, `groq` |
| Data | Supabase Postgres 17 + pgvector 0.8 (768-d vectors), RLS on every table |
| Storage | Cloudflare R2 (10 GB free, zero egress) — *not yet configured* |
| Code execution (planned) | Judge0 (decision pending — see §8) |
| Hosting (planned) | Vercel (web) + Render free (API) + Supabase free |
| Tests | pytest: 283 passing + 3 strict known-bug markers; tsc / eslint / `next build` clean |

**Trust model:** Next.js owns light CRUD (resume metadata/upload, auth). FastAPI owns anything touching an LLM, embeddings or (later) voice. The browser calls FastAPI directly with the Supabase JWT; FastAPI verifies it and uses the **service role**, so ownership is enforced in code (every query is scoped by `user_id`).

### 3.1 Repository map
```
apps/web   app/(auth)  sign-in · account-setup · onboarding · sign-up(demo)
           app/(dashboard)  dashboard · chat · interviews(+setup,+[id]) · ats-score · resumes
                            reports(stub) · settings/api-keys · settings/team(stub) · admin/question-bank
           app/api/resumes (upload/list/delete) · app/auth/callback · proxy.ts
           lib/ (supabase clients, api-client, auth guards, storage)  components/ (ui, chat, settings, interview, ats, three)
apps/api   app/core · keys · chat · rag(+parsing) · ats · interviews(+types, voice[empty]) · llm(+prompts) · providers · coding[empty] · reports[empty]
           migrations/0001–0019 · tests/ (unit + tests/integration)
docs/      IMPLEMENTATION.md · PROJECT_DOCUMENTARY.md · PILLARS_PLAN.md · PRODUCT.md
```

### 3.2 HTTP API (FastAPI)
`GET /health`, `GET /health/authenticated` · **Keys:** `POST/GET /keys`, `DELETE /keys/{id}` · **Chat:** `POST/GET /chat/conversations`, `GET|POST /chat/conversations/{id}/messages` (POST streams text) · **RAG:** `POST /rag/resumes/{id}/process` · **ATS:** `POST /ats/score` · **Interviews:** `POST /interviews`, `GET /interviews`, `GET /interviews/{id}`, `GET …/transcript`, `POST …/turns`, `POST …/complete`; question bank `GET|POST /interviews/question-bank`, `PATCH|DELETE …/{id}` (permission-gated) · **Usage:** `GET /usage`. Next route handlers: `GET|POST /api/resumes`, `DELETE /api/resumes/{id}`, `/auth/callback`.

### 3.3 Data model (live, 14 tables, RLS on all)
`profiles` · `roles` · `admin_permissions` · `provider_keys` · `notifications` · `resumes` (+`digest`) · `resume_chunks` (vector 768) · `conversations` · `chat_messages` · `interviews` (+`brief`, `summarized_through_turn`, `running_summary`, `selected_question_ids`, `provider`) · `interview_transcripts` · `question_bank` (vector 768) · `interview_reports` (unused yet) · `llm_usage` (daily per user/provider/kind). Migrations `0001–0018` applied; `0019_audit_hardening` applied on 2026-10-02.

---

## 4. How things work, step by step

**Sign-in → dashboard.** Google OAuth → callback → no `profiles` row? → account-setup (set password, create profile; trigger assigns role, first user = Owner) → no valid primary Gemini key? → onboarding → dashboard.

**Saving a key.** Browser → `POST /keys` → backend **validates first** (Gemini lists models; others a tiny call) → only a valid key is encrypted and upserted; invalid/rate-limited/outage ⇒ clear error and nothing stored.

**Every LLM call (the gateway).** Feature builds messages + `LLMOptions(task, caps, temperature, json_mode)` → `gateway.complete/stream/embed` → per-user rate limiter (queues ≤20 s) → provider adapter → retry on overload (2×) → on rate-limit, failover to the backup key (+notification) → usage recorded. Errors map to 412 no key · 429 quota · 503 overloaded · 400 key rejected · 422 reply blocked. Nothing is retried/failed over once output has started.

**Chat.** Window of last 10 messages → streamed reply (first chunk pre-fetched so early errors are real JSON errors) → both messages saved when the reply completes.

**Resume upload.** Browser → Next route (validate extension + file signature + size) → R2 → `resumes` row → FastAPI process: download → parse → section-aware chunks (≤60) → **one** batched embed → digest (non-fatal) → store chunks, then mark `parsed_text` last (a failure leaves it retryable).

**ATS score.** Extract requirements (JSON mode, cached) → one batched embed of the terms → per-term best-chunk similarity → keyword (whole-word + synonyms) + semantic + formatting → composite → feedback call. Empty requirements ⇒ 422 (not a fake high score).

**Interview.** *Start:* validate resume/key → 1 embed of the JD → pick questions from the bank (coding/webd 2, sde 1) → 1 JSON-mode call returning `{brief, opening}` (fallback if malformed) → status `in_progress`, `ends_at = now+60 min`. *Each turn:* phase from elapsed time → system prompt (type + phase goal + brief + current question for coding types only during problem phases) + summary + last turns → 1 call (≤160 tokens) → save user+AI turns together → incremental summary every 8 turns (failure never fails the turn). *Time up:* >60+5 min ⇒ completed, 409.

| Interview type | Phases (minutes) | Coding platform | Bank questions |
|---|---|---|---|
| Coding | intro 5 · problem_1 25 · problem_2 25 · wrap_up 5 | yes | 2 |
| Web Dev | intro 5 · problem_1 25 · problem_2 25 · wrap_up 5 | yes | 2 |
| SDE | intro 5 · coding 20 · system_design 20 · behavioral 10 · wrap_up 5 | yes | 1 |
| Behavioral | warm_up 5 · questions 45 · wrap_up 10 | no | 0 |
| HR | warm_up 5 · questions 40 · wrap_up 15 | no | 0 |
| ML/AI | intro 5 · concepts 25 · case_study 25 · wrap_up 5 | no | 0 |
| System Design | intro 5 · design_discussion 45 · wrap_up 10 | no | 0 |
| Case Study | intro 5 · case_presentation 10 · discussion 35 · wrap_up 10 | no | 0 |

---

## 5. Complete decisions log

**Product & scope**
1. Fresh rebuild (earlier project erased); single-tenant; roles Owner/Admin/User with per-admin granular permissions.
2. Three services; build order Chat → RAG → ATS → Interviews so the provider/failover plumbing is proven on the simplest service first.
3. Interview types: the original six plus **System Design** and **Case Study**. Fixed **1 hour**, per-type phases. Timed mode only; **practice mode deferred**; **recording declined**; **anti-cheat deferred**.
4. Interview = Gemini + Groq only (Claude lacks native audio). Voice is the flagship experience.
5. ATS: **no history persisted**; sub-scores always shown; reuses the same resume pipeline.
6. Reports: downloadable for **exactly 7 days**, then purged.
7. Question bank: Owner (+Admins with `manage_question_bank`) only; test cases are an answer key and must never reach candidates.

**BYOK & auth**
8. Gemini mandatory (embeddings are Gemini-only); Claude/Groq optional; primary + backup keys; Fernet encryption; server-side validation; silent failover then notify.
9. **Google-only** sign-in; the password is just an alternate login. (A temporary demo sign-up exists for development and must be deleted.)

**Infrastructure**
10. Everything free: Vercel + Render + Supabase + R2 ($0/month). Supabase Storage replaced by **R2** (10 GB, no egress). **Redis dropped** (no cache layer for now). Judge0 hosted rather than self-hosted *(revisited — see §8)*.
11. Monorepo `apps/web` + `apps/api`. Two-layer backend: Next route handlers for light CRUD, FastAPI for AI.
12. pgvector inside Postgres (no separate vector DB); embeddings `gemini-embedding-001` at 768 dims (the retired `text-embedding-004` was replaced).

**LLM architecture (approved 2026-10-02)**
13. All model traffic through **one gateway**; prompts short, structured, capped (output capped in the prompt *and* `max_output_tokens`); JSON mode over prose; never resend distilled data (JD→brief, turns→summary, resume→digest); first message to a provider is always a user turn.
14. Default Gemini model is the **lite** alias (~0.9 s to first token vs 6–7 s for the thinking flash model; 500 vs 20 requests/day on free tier).
15. Embeddings batched (one request per list). Chat window 10 messages. ATS requirements cached in memory only.
16. Quotas are **per Google project**, reset at midnight **Pacific**; a backup key only helps if it is from a different project.

**Working agreements**
17. Discuss → finalize → written plan → approval → implement; every executed step is logged in the documentary (Action / Why / Result / Problems).
18. **No live LLM-provider calls by the assistant** (free-tier quotas are tiny): verification uses mocks, tsc/eslint/build, and the user tries live paths in the UI.
19. Frontend files: `page.tsx` is a thin re-export of a properly named `XView.tsx`.
20. Migrations are applied only with explicit go-ahead; secrets are never typed, logged or documented.
21. Commit trailer: `Co-Authored-By: Claude Sonnet 5.5`.

---

## 6. What has been built (chronological)

| Date | Step | Outcome |
|---|---|---|
| 09-27 | **Planning** | Scope, stack, schema, 10-phase plan written and approved |
| 09-30 | **Phase 1** — foundation | Monorepo, Supabase project + migrations 0001–0010, Google auth flow, account setup, role trigger, guards, design system, dashboard shell, JWT verification |
| 10-01 | **Phase 2** — BYOK | Adapters (Gemini/Claude/Groq), Fernet encryption, validation, failover, onboarding + settings UI |
| 10-01 | Demo sign-up; file-naming cleanup; theme-toggle redesign | Dev convenience page (temporary); `page.tsx` + named views; icon toggle |
| 10-01 | **Phase 3** — Chat | Conversations, streaming, provider selector |
| 10-01 | **Phase 4** — RAG foundation | R2 storage wrapper, parsing, chunking, embeddings, pgvector RPCs, resume upload UI |
| 10-01 | **Phase 5** — ATS | Requirements extractor, scorer, feedback, ATS UI |
| 10-01 | **Phase 6** — Interview core (text) | Orchestrator, 8 types, question bank CRUD, setup + room UI, summarizer |
| 10-02 | **First live run** | Real Google sign-in, onboarding, encrypted key, streamed chat verified; found/fixed ES256-vs-HS256 token bug, `.env` path bug, retired Gemini models, 503 handling, slow model |
| 10-02 | **LLM architecture steps 1–6** | Foundation, batching, gateway (limiter/failover/usage, `llm_usage` + migration 0017), interview diet (migration 0018), ATS diet, chat window + `/usage` + "Used today" |
| 10-02 | **Self-audit** | Fixed raw-JSON greeting, early question reveal, summary failing a turn, turn-order; blocked-reply 422; eslint errors; gateway docs |
| 10-02 | **Phase 1–6 audit by 3 agents** | 132 integration tests added; fixes across auth (forgery hole), keys, ATS, interviews, RAG, frontend; migration 0019 written |
| 10-02 | **Pillars plan (RAG/LLM/backend)** + risk research | `docs/PILLARS_PLAN.md` rev 2 — approved |
| 10-02 | **M0 safety net** | 0019 applied live; startup config validation; CORS/docs from env; CI workflow; Claude IDs fixed; `docs/FACTS.md`; 4 MB upload limit |

**Quality gates today:** 283 backend tests pass (+3 deliberate known-bug markers), `tsc`, `eslint`, `next build` clean. Nothing about R2/resume upload, ATS, interviews, Claude, Groq or batched embeddings has run against real services yet.

---

## 7. Current state at a glance

- **Verified live:** Google sign-in, account setup, Owner role, onboarding, encrypted Gemini key, streamed chat.
- **Built but unverified live (blocked on R2 credentials or a first manual run):** resume upload/processing, ATS, interview setup and turns, question-bank UI, Claude and Groq adapters, batched embeddings.
- **Credentials:** Supabase keys in `apps/api/.env` (gitignored); Gemini key stored for the Owner; **no R2, Groq or Claude keys**.
- **Open items:** delete the demo sign-up; notifications and key-delete UI; "Leaked Password Protection" is a dashboard toggle (user's choice).
- **Known weaknesses being addressed by the pillars plan:** no timeouts/deadline on provider calls, truncation not detected, prompt-injection exposure, long work runs inside one request, non-atomic multi-step writes, ATS semantic score uncalibrated, no retrieval evals, any signed-in user can read the question bank.

---

## 8. What comes next

### 8.1 Proposed plan (awaiting approval) — `docs/PILLARS_PLAN.md`
Strengthen the three pillars (**RAG pipeline, LLM pipeline, backend architecture**) *before* the hard features so Phases 7–9 inherit them.

| Milestone | What | Needed by |
|---|---|---|
| **M0 Safety net** ✅ done 2026-10-02 | 0019 applied; startup config validation + CORS/docs from env; CI workflow; Claude model IDs fixed; `docs/FACTS.md`; interim 4 MB upload limit | — |
| **M1 Platform core** | Unified error codes + request ids + JSON logs; owner-scoped repository layer; "waking the server" UI; rate limits; pagination | everything |
| **M2 LLM hardening** | Thinking control, timeouts + deadline, finish-reason handling, error taxonomy, streaming-disconnect safety, structured output + repair, prompt-injection defense, background summaries, per-key limiter, Pacific-day usage, adapter fixture tests + user-run smoke script | Phases 7, 8, 9 |
| **M3 RAG v2** | Eval harness first; embedding task types + normalization + versioning (re-embed is free: tables empty); chunker v2; one-call multi-term retrieval; calibrated ATS; question selection with diversity/difficulty/exclusion; **question-bank lockdown** | Phase 7 |
| **M4 Jobs & atomicity** | `jobs` table + runner + polling; atomic RPCs (turn append, chat exchange, chunk replace); direct-to-R2 upload; real `setting_up` job with progress | Phases 7–9 |

### 8.2 Remaining product phases
| Phase | Scope | Key dependency |
|---|---|---|
| **7 — Coding platform** | Monaco editor beside the transcript; submissions run against hidden/visible test cases through an `ExecutionBackend` (Judge0 first); results can inform the interviewer; code enters prompts as untrusted data | M2 + M3 + M4; **execution-backend decision** |
| **8 — Voice** | TTS/STT, VAD, silence + interruption handling, live transcript; prototype decides Gemini Live (15-min sessions need resumption) vs STT+LLM+TTS; migrate to `google-genai` first; WebSocket ticket auth | M2 streaming |
| **9 — Reports** | Report job (structured per-section scoring, injection-resistant), `expires_at` = +7 days enforced at read, purge via `pg_cron`, presigned download, reports page with countdown | M4 jobs |
| **10 — Polish & launch** | Dockerfile/Render config, `/ready`, CORS for the Vercel domain, Supabase redirect URLs, delete demo sign-up, accessibility + reduced motion, error-state sweep, Playwright smoke | all |

### 8.3 Decisions still needed from you
(Plan approved and M0 done on 2026-10-02.) 3. Confirm re-embedding now is fine (vector tables are empty) and whether to compare `gemini-embedding-2`. 4. OK to migrate to `google-genai` before voice. 5. OK with direct-to-R2 upload and `pg_cron` expiry. 6. Keep-warm pinger for Render (one service ≈744 of 750 free hours)? 7. **Code execution:** paid hosted Judge0 (~€27/mo, 2,000 runs/day), self-hosted Judge0, or demo on the free shared key (≈50 runs/day) first. 8. Provide **Cloudflare R2 credentials** (needed to run resumes → ATS → interviews live) and, optionally, Groq/Claude keys.

---

## 9. Verified external facts (checked 2026-10-02)
Render free: spins down after 15 min idle, ~1 min cold start, 750 instance-hours/month, ephemeral disk, WebSockets supported. Vercel: 4.5 MB request/response body cap; Hobby function max duration 300 s. Gemini: daily quotas reset at midnight Pacific, limits per project; `gemini-embedding-001` needs manual normalization below 3072 dims and takes ≤2,048 input tokens; lite models think by default (thought tokens billed separately); Live API audio sessions capped at 15 min (extendable with compression/resumption), 128k context, PCM 16 kHz in / 24 kHz out. Claude current IDs: `claude-sonnet-5-5`, `claude-opus-5-5`, `claude-fable-5-1`, `claude-haiku-4-5-20251001`. Groq production: `llama-3.1-8b-instant`, `llama-3.3-70b-versatile`, Whisper STT. Judge0: self-host free; official hosted from ~€27/mo (2,000/day); the free shared RapidAPI key is reported at ~50/day. **Still unmeasured:** real Gemini 429/503 error bodies, real latency of our model alias, Live API concurrency.

---

## 10. How to run and verify

```bash
# API (from apps/api; venv at apps/api/venv)
source venv/Scripts/activate && python -m pytest -q          # 283 passed, 3 xfailed
# Web (from apps/web)
npx tsc --noEmit && npx eslint . && npx next build
```
Dev servers are defined in `.claude/launch.json` (`web` on :3000, `api` on :8000 launched from the repo root with `--app-dir apps/api`; the API has no auto-reload — restart after backend edits). Environment files: `apps/api/.env` and `apps/web/.env.local` (never committed; values never recorded in docs).
