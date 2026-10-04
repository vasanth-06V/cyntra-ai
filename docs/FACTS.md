# External facts the product depends on

Each fact: what, source, date verified. Format: `fact — source — verified`.
Last reviewed: **2026-10-04**. Facts dated 2026-10-02 were read from the providers' documentation; **none of them has been confirmed by a live measurement** unless it says "measured". Re-check before relying on a model name, and before launch.

Legend: **verified** = read in provider documentation on the date shown (not measured on our own stack); **measured** = observed on our own stack; **unverified** = assumed, not checked; **obsolete** = no longer used by the product (kept as history).

## Hosting
- Render free web service spins down after 15 min without inbound traffic; cold start about 1 min; 750 free instance-hours/month per workspace; ephemeral filesystem; WebSockets supported and count as traffic; no inbound private-network traffic — https://render.com/docs/free — verified 2026-10-02
- Vercel Functions: request/response body cap 4.5 MB; Hobby max duration 300 s (default and maximum); 2 GB / 1 vCPU — https://vercel.com/docs/functions/limitations — verified 2026-10-02
- Whether Render's free plan runs two instances side by side during a deploy (matters because boot recovery fails every active job) — **unverified**
- Measured Render cold-start time — **unverified** (the app shows a "waking the server" banner and retries; the real figure was never measured)
- Render/Vercel limits above are the published free-plan figures; confirm in the dashboards at deploy time — **unverified for this account**

## Supabase
- Storage is used through the S3-compatible endpoint with a project S3 access key (keys are project-wide, not bucket-scoped); the bucket `resumes` is private with a 512,000-byte limit and PDF/DOCX only — measured 2026-10-03 (live check through the app's Python and Node clients: PDF and DOCX accepted, `text/plain` and `image/png` rejected with 415, 600 KB rejected with 413, 499 KB accepted, path-style addressing works, a missing object returns a bare 404 with an empty error code)
- Free tier: 500 MB database, 1 GB storage, project pauses after about a week of inactivity; past the database limit the project goes read-only — published figures quoted by the final audit — **unverified for this project** (live usage on 2026-10-04: database 12 MB, 1 storage object of 143 KB)
- A paused project makes the API's `/ready` answer 503 and every page error until the owner resumes it in the dashboard — **unverified** (reasoned from the pause rule)
- `max_connections` of the free tier is irrelevant: the API uses the HTTP (PostgREST) client — audit reasoning, **unverified**
- Auth settings (email sign-up enabled? confirm-email?), legacy HS256 JWT secret still active? — not visible from SQL — **unverified**; check in the dashboard (Authentication)
- Leaked-password protection is **off** (security advisor WARN, 2026-10-04); may need a paid plan to enable — **unverified**
- How PostgREST surfaces SQLSTATE P0002 (raised by the atomic RPCs) to supabase-py — **unverified** (audit L-07)

## Gemini
- Rate limits are per project (not per key); daily (RPD) quotas reset at midnight Pacific time — https://ai.google.dev/gemini-api/docs/rate-limits — verified 2026-10-02
- `gemini-embedding-001`: task types SEMANTIC_SIMILARITY, CLASSIFICATION, CLUSTERING, RETRIEVAL_DOCUMENT, RETRIEVAL_QUERY, CODE_RETRIEVAL_QUERY, QUESTION_ANSWERING, FACT_VERIFICATION; output dimensionality 128–3072 (768/1536/3072 recommended); dimensions other than 3072 must be normalized manually (the product L2-normalises); 2,048 input tokens — https://ai.google.dev/gemini-api/docs/embeddings — verified 2026-10-02
- Thinking: reported separately (thought tokens) and billed with output; default-on for gemini-3.8-flash (medium) and gemini-3.5-flash-lite (minimal); off by default for gemini-2.5-flash-lite — https://ai.google.dev/gemini-api/docs/thinking — verified 2026-10-02
- Error handling guidance: retry 429/408/5xx with exponential backoff and jitter; the docs do not specify retry-delay or quota-type fields in 429 bodies — https://ai.google.dev/gemini-api/docs/troubleshooting — verified 2026-10-02
- The default model is the alias `gemini-flash-lite-latest` (not a pinned ID): about 0.9 s to first token versus 6–7 s for `gemini-flash-latest` — **measured 2026-10-02** (during the first live run; the alias can be repointed by Google at any time, audit M-05)
- Live API (audio sessions limited to 15 min, 128k context, PCM 16 kHz in / 24 kHz out, automatic VAD) — https://ai.google.dev/gemini-api/docs/live-api/capabilities — verified 2026-10-02 — **obsolete**: voice is browser-side; the Live API is not used
- `google-generativeai` deprecation in favour of `google-genai` — **obsolete**: the Gemini adapter is plain REST over httpx; neither SDK is a dependency

## Claude
- Current API IDs: `claude-fable-5-1`, `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-4-5-20251001`; Sonnet 5.5 adaptive thinking; Haiku 4.5 retirement not sooner than 2026-10-15; `claude-sonnet-5` is a legacy model — https://platform.claude.com/docs/en/models/overview — verified 2026-10-02. The product uses `claude-sonnet-5-5` for every task (the "fast" tier points at Sonnet too until Haiku is re-evaluated). Never exercised with a real key — **unverified live**

## Groq
- Production models include Llama 3.1 8B (`llama-3.1-8b-instant`), Llama 3.3 70B (`llama-3.3-70b-versatile`), OpenAI GPT-OSS 20B/120B, Whisper speech-to-text — https://console.groq.com/docs/models — verified 2026-10-02. The product uses the 8B for cheap tasks and the 70B for the rest. Never exercised with a real key — **unverified live**. Whether Groq free-tier tokens-per-minute limits fit the report prompt (about 8.5k tokens) — **unverified** (audit BE-M6)

## Browser voice (used by the interview room)
- Chrome and Edge provide speech recognition (`SpeechRecognition` / `webkitSpeechRecognition`); Chrome's recognizer needs internet and sends audio to Google; Firefox has no speech recognition (the room falls back to typing); Safari support is partial — stated in `docs/PHASE8_PLAN.md`, **unverified by testing** (the owner has not yet tried voice; behaviour per browser, per microphone and per accent is unmeasured)
- Browser speech synthesis uses system voices (quality varies by OS and browser) — **unverified**
- Open microphone while the interviewer speaks can pick up the speakers (echo); the room is turn-taking by default and offers an "allow interrupting (use headphones)" option — design assumption, **unverified**

## Monaco editor
- `@monaco-editor/react` loads the editor files at runtime from a third-party CDN (jsdelivr) by default; no offline fallback or integrity check; a future Content-Security-Policy must allow it or the files must be self-hosted — read from the code by the frontend audit (M-14), **unverified in a browser with the CDN blocked**

## Judge0 (**obsolete**)
- Self-hosting is free; official hosted plans reported at about EUR 27/month for 2,000 submissions/day; the free shared RapidAPI key reported at about 50 requests/day (anecdotal) — web search results — 2026-10-02. **The Judge0 plan was withdrawn on 2026-10-03: no code is executed.** Kept only as the record behind that decision.

## Assumed from documentation, awaiting evidence (record with `python -m scripts.llm_smoke --record`, owner-run)
- Gemini REST: `generateContent`, `streamGenerateContent?alt=sse`, `models/gemini-embedding-001:batchEmbedContents`, `GET /models`; key via `x-goog-api-key` header
- **`thinkingLevel: "minimal"` acceptance.** `generationConfig.thinkingConfig` takes `thinkingBudget` or `thinkingLevel`; whether `thinkingLevel: "minimal"` is accepted for `gemini-flash-lite-latest` is unverified. The adapter drops the setting automatically if the API rejects it (so the worst case is more thought tokens eating the output cap)
- **Gemini REST error bodies.** 429 bodies are assumed to be standard Google error JSON with `QuotaFailure` / `RetryInfo` details; the quota type is parsed from `quotaId` containing PerDay/PerMinute. Real 429/503/400 bodies were never recorded
- **Claude and Groq model IDs and parameters**: IDs above are from documentation only; Claude `temperature` handling and typed stop reasons are unverified with the pinned `anthropic==0.40.0` and `groq==0.13.1` SDKs
- **Embedding quality**: the ATS semantic window `LOW`/`HIGH` in `app/ats/semantic.py` (placeholders 0.55 / 0.80 as of 2026-10-04) is uncalibrated against the real model until `scripts/rag_eval_live.py` is run
- **Judge and report quality**: how well the real model reviews code and scores reports is unmeasured until `scripts/judge_eval_live.py` and `scripts/report_eval_live.py` are run

## Not yet measured (to be recorded by the owner-run scripts)
- Real Gemini 429/503/400 response bodies and any retry/quota fields
- Time to first token and thought-token counts for the configured Gemini alias at the current date (the 2026-10-02 figures above predate the REST rewrite)
- Measured Render cold-start time
- Voice recognition accuracy and behaviour per browser
- Judge agreement with labelled solutions; report score ordering (strong > average > weak) and injection resistance
- Whether the free-tier Groq limits accommodate the report and review prompts
