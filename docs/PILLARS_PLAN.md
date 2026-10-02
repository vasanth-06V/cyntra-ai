# CyntraAI — the three pillars: audit and plan

Status: **PROPOSED — awaiting the user's approval. Nothing in this plan has been implemented.**
Sources: three independent read-only audits (RAG, LLM, backend) run on 2026-10-02 against commit `4f81442`, each rated against best practice with file/line evidence. Claims below were verified in code/DB unless marked *(to verify)*. No live provider calls were made.

---

## 1. Verdict: are we following the three pillars?

**Partly. The foundations are right; the production-grade layers are missing.**

| Pillar | What is already good | What is missing (biggest first) |
|---|---|---|
| **RAG** | One batched embed per ingest; digest instead of raw chunks in interviews; tenant checks before every retrieval; exact scan is the right index at this size | No embedding `task_type` (doc vs query) and no L2 normalization; resume chunker misses common headings and cuts mid-bullet; ATS semantic score is uncalibrated (a resume with *none* of the skills still scores ~50%) and costs ~20 DB calls; **no retrieval quality test of any kind**; no embedding-model versioning; non-atomic re-ingest; **any signed-in user can read the whole question bank incl. hidden test cases** |
| **LLM** | Single gateway; failover/retry/limiter/usage; token-lean prompts; incremental summary; blocked-reply handling | **No timeouts/deadline** (a hung call can block 10 min; SDK retries stack under ours); no `finish_reason` (truncated replies are saved as normal turns); chat/usage lost on client disconnect; **prompt injection** (stored brief/summary re-enter the *system* role); error mapping wrong (bad request ⇒ "key rejected", retired model ⇒ "overloaded"); limiter buckets per user, not per key/project; no observability; no eval; adapters are text-only (no structured output, no stream events) |
| **Backend** | Thin routers; consistent owner-scoping by convention; input limits; JWT done right; 276 tests + integration suite | **Everything long runs inside one request** (resume processing, interview setup, ATS) — breaks on Render cold start / Vercel limits; non-atomic multi-step writes and a turn-index race (**migration 0019 is still unapplied live**); no repo layer (ownership by convention, helpers duplicated 3×); no startup validation, CORS hard-coded to localhost, no error codes/request ids/structured logs, no Dockerfile/CI/readiness; DB calls via thread pool |

Cross-cutting insight: the three pillars share four missing primitives. Build them **once**, then every feature (and Phases 7–9) inherits them:

1. **Error envelope + request id + structured logs** (backend) — the LLM and RAG layers need it for observability.
2. **Jobs + atomic RPCs** (backend) — resume ingest, interview setup, code runs and reports are all "long, idempotent, resumable" work.
3. **`Completion`/stream events with `finish_reason`, timeouts and a deadline** (LLM) — voice, reports and truncation handling all need it.
4. **Embedding `kind` + normalization + versioning + an eval harness** (RAG) — ATS, question selection and reports all depend on retrieval being measurable.

---

## 2. Design decisions (conflicts between audits resolved)

| # | Decision | Why |
|---|---|---|
| D1 | Single backend instance stays (no Redis/queue/microservices). Jobs live in a Postgres `jobs` table run by asyncio tasks, with startup recovery. | Free-tier realism; Render restarts kill tasks, so the table is the source of truth. |
| D2 | Embeddings stay `gemini-embedding-001` @768. Add `task_type` (DOC for chunks/questions, QUERY for JD/keywords), L2-normalize in `llm/` (embeddings moves under `llm/`), record `embed_model` per row. **Do the re-embed now — all vector tables are empty.** | Cheapest moment; fixes quality before data exists. |
| D3 | No HNSW on `resume_chunks` (per-resume slice is tiny; exact scan is optimal). Question bank: exact scan until ~10k rows, then HNSW. | Filtered ANN loses recall on tiny slices. |
| D4 | ATS semantic score becomes a **calibrated coverage** (threshold + hybrid keyword hit), one multi-term RPC; constants set from the eval harness, and the user runs one rate-safe live calibration. Until calibrated, semantic weight in the composite is reduced. | Current score compresses everything into ~0.55–0.75. |
| D5 | Rate-limit buckets keyed by `(provider, key-hash)`, with priority lanes (interactive > background). | Gemini free quota is per project/key; backup keys then get their own budget. |
| D6 | SDKs: set explicit timeouts and `max_retries=0` now; **migrate `google-generativeai` → `google-genai` before Phase 8** (needed for Live API, schema output, thinking budget). | Deprecated SDK + private-attribute hack; Live API only exists in the new one. |
| D7 | Untrusted text (JD, resume, brief, summary, answers, code) is delimited and never placed in the system role; replies pass a cheap leak filter. Reports treat the transcript as quoted data and bound scores by schema and Judge0 results. | Second-order injection is real today and becomes an integrity issue in Phase 9. |
| D8 | Resume upload moves to **presigned direct-to-R2 + one `POST /v1/resumes` (register + enqueue) + job polling**. | Removes the Vercel 4.5 MB / 10 s limits and the double hop. |
| D9 | Report expiry: `expires_at` defaults in the DB, enforced at read time, swept by `pg_cron` (DB rows) plus an opportunistic job (R2 objects). | Works even if the free instance sleeps. |
| D10 | Phase 8 voice: **decide Gemini Live vs STT+LLM+TTS with a small user-run prototype first**; both sit behind one `VoiceSession` interface. | Live API free-tier limits are unconfirmed *(to verify)*. |

---

## 3. Milestones (ordered; each independently testable and committed; DB migrations are batched and need the user's go-ahead each time)

### M0 — Safety net (S)
- **Apply migration 0019** (already written: first-Owner lock, resume FK `SET NULL`, unique `(interview_id, turn_index)`, unique permission grant, revoke direct client writes, hide `encrypted_key`, revoke `anon`). Turns the 2 migration-dependent xfail tests green.
- Settings: required fields validated at startup (valid Fernet key, Supabase URL…), `CORS_ORIGINS` and docs toggle from env, `/health` stops leaking `environment`.
- GitHub Actions workflow: pytest + tsc + eslint + build.

### M1 — Platform core (M) *(unblocks everything)*
- `core/errors.py`: `AppError(code,status,message)` + stable codes (`unauthorized, forbidden, not_found, key_missing, key_rejected, quota_exhausted, provider_overloaded, reply_blocked, validation_failed, conflict, job_failed`); handlers for `AppError`/`HTTPException`/validation/catch-all, installed so errors keep CORS headers. Frontend `fastapi.ts` reads `error.code/message` (old `detail` kept one release).
- Request-id middleware + JSON access log (no tokens/prompts).
- Repo layer `db/repo.py`: owner-scoped helpers (`repo.resume(id)`, `.interview(id)`, `.conversation(id)`), one place for `.table(`; move `get_key_row`/`notify_user` out of `keys/service`; **architecture test** forbidding `.table(` outside `db/`; delete the 3 duplicated `_get_owned_*`.
- Rate limits on `/keys`, `/ats/score`, `/rag/*`; bounded limiter eviction; pagination on list endpoints; DB `LIMIT` for chat history.

### M2 — LLM hardening (M–L) *(blocks Phase 7/8/9 quality)*
1. Timeouts per task, SDK `max_retries=0`, one `deadline` around limiter-wait + attempts; backoff with jitter and `Retry-After`.
2. Error taxonomy: `ProviderBadRequest` (→400/502, generic), `ProviderTimeout` (→504), `ProviderConfigError` (retired model: not retried, loud), `RateLimit(kind=rpm|rpd, retry_after)`; `InvalidArgument` stops meaning "key rejected" outside validation.
3. `Completion` (+`finish_reason`, usage incl. thought tokens, model, latency, TTFT) and `StreamEvent`; truncated prose trimmed to a sentence boundary; JSON truncation retried once with a higher cap.
4. Streaming `try/finally`: usage recorded and **partial chat reply persisted** on disconnect/error (`chat_messages.status`); closes the third xfail.
5. Structured output: pydantic schemas (`llm/schemas.py`), `complete_structured` (parse → one repair retry → typed fallback), `raw_decode` parser, Gemini `response_schema`, Claude via forced tool, Groq `json_object`+validate; capability flags.
6. Injection standard (D7) + offline injection corpus tests; leak filter on interviewer replies.
7. Summary update and resume digest moved off the request path (background, retryable).
8. Per-key-hash limiter + priority lanes + exhausted-key cooldown (D5); model pins + fallback list (replace `-latest` in prod).
9. Observability: one JSON log line per LLM call (feature, task, model, tokens, latency, TTFT, outcome, retries, failover); `llm_usage` gains `feature`/`model`; prompt registry stamps `prompt_id/version` on stored briefs/summaries.
10. Recorded-fixture **adapter contract tests** (Gemini/Claude/Groq) + an opt-in, rate-safe `scripts/llm_smoke.py` for the *user* to run (≤10 requests, spaced; also records fixtures).

### M3 — RAG v2 (M–L) *(order: eval harness first, so every later change is measured)*
1. **Eval harness** `tests/rag_eval/`: golden resume/JD pairs, deterministic fake embedder for CI (tests chunking/normalization/RPC contract/calibration/MMR), metrics (recall@k, section hit, good-vs-bad resume score separation, monotonicity), `--live` mode for the user (≤50 requests; prints similarity histograms to set constants).
2. Embedding standard (D2): `kind=doc|query`, `title=section`, L2-normalize, `embed_model/embed_version`, query-embedding cache keyed `hash(model|task|text)`.
3. Chunker v2: text normalization, wide heading aliases + ALL-CAPS heuristic, role-block and bullet-aware splitting (~150–300 tokens), contextual header `"{section} | {role}"`, extra skills-list chunk, `section` stored, warning when the 60-chunk cap trips.
4. SQL: `match_resume_chunks_multi` (one call for all keywords, hybrid `tsvector` hit), `match_question_bank_v2` (exclusion, candidate set), atomic `replace_resume_chunks`, `content_hash` skip on re-process.
5. ATS recalibration (D4): query template ("Experience with X"), calibrated coverage, must 2× / nice 1×, evidence chunk+section per requirement fed to the feedback prompt.
6. Question selection: `difficulty`/`topic` columns, MMR over 12 candidates, per-type diversity, exclude already-asked, jitter; select by **extracted requirements**, not whole-JD.
7. **Question-bank lockdown** (revoke client SELECT / `EXECUTE` on match RPCs; backend serves candidates only visible data).
8. Re-embed script (`embed_model <> CURRENT`), user-run.

### M4 — Jobs, atomicity, upload (M–L)
- `jobs` table (queued/running/succeeded/failed, progress text, heartbeat, partial-unique index for idempotency), asyncio runner with a 2-job semaphore, startup recovery, `GET /v1/jobs/{id}` (owner-scoped).
- Atomic RPCs: `append_interview_turns` (row lock, both turns in one insert), `append_chat_exchange`, plus a per-interview in-process lock and optional `Idempotency-Key` (double-click no longer double-spends LLM calls).
- Presigned direct R2 upload + `POST /v1/resumes` (D8); interview setup becomes a real `setting_up` job with progress messages (the plan's "polled setup screen"); frontend polling UI.
- Async supabase client in lifespan, drop `to_thread` wrappers (after the repo layer makes it a one-file change).

### Phase 7 — Coding platform *(starts after M0–M4; M2 items 1–6 and M3 items 6–7 are hard prerequisites)*
- `code_submissions`, `test_results` (+ `is_hidden`); Judge0 client with reused httpx, global Judge0 limiter, batch submit + poll as a `code_run` job; hidden cases never leave the backend (only pass/fail + counts).
- Question/code/results enter prompts as delimited untrusted blocks with a code-aware token cap; leak filter active; Monaco UI polls job status.

### Phase 8 — Voice
- Prerequisites: M2 stream events + cancellation, background summaries, `google-genai` migration (D6).
- User-run prototype decides Live API vs STT+LLM+TTS (D10) → `VoiceSession` interface, WebSocket **ticket** auth (single-use, 30 s; never the JWT in the URL), session state rebuilt from `interview_transcripts`.

### Phase 9 — Reports
- `report_generate` job: evidence pack (per-phase summary + key quotes + Judge0 results + rubric + JD/resume digest) → one structured call per section → deterministic aggregation → short narrative; per-section retry and partial results; stronger model only here.
- Injection-resistant judging (D7); `expires_at` DB default + read-time enforcement + `pg_cron` sweep; presigned download. RAG supplies requirement-vs-evidence via the multi RPC with zero new embed calls (requirement list stored at setup).

### Phase 10 — Deploy & polish
- Dockerfile (1 worker — limiter/cache/semaphore are per-process), `render.yaml`, `/ready`, CORS from env, docs off in prod, Supabase redirect URLs for the Vercel domain, **delete the temporary demo sign-up**, OpenAPI snapshot diff in CI (+ generated TS types), a few real-Postgres tests (RPCs/constraints/RLS), accessibility + reduced motion, Playwright smoke, `MultiFernet` rotation, drop unused deps.

---

## 4. Migration batches (each applied only with the user's explicit go-ahead)

| File | Contents | When |
|---|---|---|
| `0019` (exists) | audit hardening | M0 |
| `0020_rag_v2` | `embed_model/section/difficulty/topic/content_hash`, tsvector+GIN, multi/v2/replace RPCs, **question_bank lockdown** | M3 |
| `0021_jobs` | `jobs` table + policies | M4 |
| `0022_atomic_rpcs` | `append_interview_turns`, `append_chat_exchange`, `chat_messages.status` | M2/M4 |
| `0023_llm_observability` | `llm_usage.feature/model`, prompt-version columns | M2 |
| `0024_coding` | `code_submissions`, `test_results` | Phase 7 |
| `0025_reports` | tighten `interview_reports`, `expires_at` default/index, `pg_cron` sweep | Phase 9 |

## 5. Verification strategy (no live provider calls by the assistant)
Unit + integration suites stay green at every step; strict-xfail tests flip as bugs are fixed; **recorded-fixture adapter tests**, **RAG eval harness**, **injection corpus**, an architecture test (no `.table(` outside `db/`), a handful of **real-Postgres tests** (RPC signatures, constraints, RLS — the in-memory fake cannot prove these), `tsc`/`eslint`/`next build`. The user runs the two opt-in live scripts (RAG calibration, LLM smoke) when ready.

## 6. Decisions I need from the user
1. **Approve this plan** (or strike/reorder milestones).
2. **Apply 0019** now (M0).
3. **Re-embed-now** is free because all vector tables are empty — confirm no data you care about exists outside the DB.
4. Comfortable with the **`google-genai` SDK migration** before Phase 8?
5. Upload redesign (D8) and `pg_cron` for report expiry — OK?
6. Keep-warm pinger for Render free tier (an uptime hack) — yes/no?

## 7. Risks and unknowns *(to verify)*
Render cold-start and Vercel body/time limits (from published behavior, unmeasured); Judge0 hosted free-tier limits; Gemini Live free-tier session limits; Gemini quota reset time (Pacific vs the UTC "used today"); Claude/Groq model IDs; real Gemini 429/503 bodies and `thinking` token accounting. M2.10 and M3.1 are designed to turn these into recorded facts with a few user-run calls.
