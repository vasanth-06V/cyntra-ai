# Phase 10 — Polish and deploy (plan, for approval)

Status: **DRAFT 2026-10-03, awaiting the owner's approval.** Nothing below is built yet.
Constraints: free tiers only (Render free for the API, Vercel Hobby for the web app, Supabase free for the database, auth and file storage). I cannot create accounts or deploy for you: I prepare every file and a step-by-step runbook, you do the clicks, then a check script verifies the result.

## 1. Where things stand
All features are built: sign-in, API keys, chat, resumes, ATS score, text and voice interviews with a coding round, reports. Migrations 0001–0027 are live. 573 backend tests and 19 frontend tests pass. What remains is making it safe to put on the internet, easy to run, and pleasant to use.

## 2. Steps

**10.1 Cleanup and hardening (code)**
- Remove what is no longer used: the Judge0 settings, `apscheduler`, `websockets` and any other unused packages (audited first, not guessed); `pytest*` move to a dev requirements file so the production image stays small.
- Key rotation: `KEY_ENCRYPTION_SECRET` accepts several keys (`MultiFernet`), so the encryption key can be rotated without losing anyone's saved API keys.
- `GET /ready` (checks the database is reachable) next to the existing `/health` (which stays dependency-free for the platform health check).
- `Dockerfile` for the API (Python 3.13 slim, non-root, **one worker** because the limiter, caches, jobs and sweep are per process, honours `$PORT`), `.dockerignore`, `render.yaml` blueprint (free plan, health check `/health`, every environment variable listed with `sync: false` so no secret is ever in git).
- `npm audit` / `pip-audit` pass: fix what can be fixed without breaking changes, document the rest.

**10.2 Quality gates (CI)**
- An OpenAPI snapshot test: any accidental change to the API shape fails CI until the snapshot is deliberately updated (a script regenerates it). Frontend types stay hand-written; code generation is not worth its upkeep here.
- Real-Postgres tests (optional, see decision 3): a CI job with a `pgvector` Postgres container applies migrations 0001–0027 on a small Supabase shim (`auth` schema, `auth.uid()`, the `anon`/`authenticated`/`service_role` roles) and checks what mocks cannot: the atomic functions (`append_interview_turns`, `append_chat_exchange`, `replace_resume_chunks`), unique indexes (one submission per problem, one active job, one report per interview), the 7-day default, and that client roles have no access to the backend-only tables.

**10.3 Product polish (frontend)**
- Accessibility pass: visible focus, labels and landmarks, the chat/transcript live regions, colour contrast in both themes, keyboard use of the voice bar and editor panel; `prefers-reduced-motion` respected by Framer Motion and the 3D loading scene.
- Finish the small open items: key-delete button with confirmation, delete confirmations elsewhere, a notifications bell (the API already writes notices such as "your key stopped working"), mobile layout check of the interview room, empty and error states.
- **Delete the temporary demo sign-up** page and its route; only Google sign-in remains.
- A minimal **Privacy** page: what is stored (your encrypted keys, resumes, transcripts, 7-day reports), what leaves the app (your prompts go to the AI provider you chose; in Chrome/Edge voice recognition is processed by Google), and how to delete things.
- A small Playwright smoke test for the public pages (home, sign-in, privacy; protected pages redirect to sign-in) with an automated accessibility scan. Signing in with Google cannot be automated, so logged-in flows stay in the manual checklist.

**10.4 Deployment (runbook: `docs/DEPLOY.md`)**
1. *Render* (API): connect the repo, pick the `render.yaml` blueprint, fill in the environment variables (Supabase URL and service key, JWT secret, encryption secret, the `STORAGE_*` set, `ENVIRONMENT=production`, `CORS_ORIGINS=<your Vercel URL>`). Startup validation refuses to boot with anything missing or still pointing at localhost.
2. *Vercel* (web): import the repo, root directory `apps/web`, set `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_API_URL` (the Render URL) and the `STORAGE_*` set.
3. *Supabase*: Authentication → URL Configuration: set the Site URL to the Vercel URL and add it to the Redirect URLs (keep localhost for development). The Google OAuth client keeps using Supabase's callback, so nothing changes in Google Cloud.
4. *Keep-warm*: Render's free service sleeps after ~15 minutes idle and takes about a minute to wake. The app already shows a "Waking the server…" banner; optionally a free uptime monitor pings `/health` every 10 minutes so first visits are fast (one always-on service uses most of Render's 750 free hours a month; fine for one service). *These Render and Vercel figures come from their published docs and are not measured.*
5. `scripts/check_deploy.py` (owner-run, read-only): hits `/health` and `/ready`, confirms the API docs are closed, and sends a CORS preflight from your Vercel origin to prove the browser will be allowed through.

**10.5 Launch checklist (`docs/LAUNCH_CHECKLIST.md`)**
- Rotate the secrets that were shared in chat sessions during development (Supabase service role key, JWT secret, storage access key) and re-enter them in Render and `.env`.
- Turn on Supabase leaked-password protection (dashboard switch; irrelevant while sign-in is Google-only, but free hardening).
- Confirm no `.env*` file is tracked, the production `CORS_ORIGINS` has no localhost, API docs return 404.
- Run the three quality scripts once with your key (`llm_smoke`, `rag_eval_live`, `judge_eval_live`, `report_eval_live`) and load the starter questions; record the results in `docs/FACTS.md` and set the ATS calibration constants.
- A manual end-to-end walk-through list covering every feature, including voice in Chrome/Edge.

## 3. Honest limits
- Free hosting means cold starts, one small instance, and quotas set by Gemini/Groq on each user's own key. It will not carry heavy traffic; it is right for a portfolio, demos and personal use.
- I cannot test the deployed site myself (no accounts, no sign-in); the check script and the manual checklist cover that.
- Voice quality and recognition depend on the browser and microphone, and Google's recognizer is outside our control.

## 4. Needed from the owner
1. Approval of this plan.
2. Confirmation of **Render (API) + Vercel (web)** as the free hosts (alternatives exist; these two match what the code and docs already assume).
3. **Real-Postgres CI tests**: yes (recommended, they catch what mocks cannot, a few hours of work) or skip.
4. **Playwright smoke test**: yes (small) or skip.
5. **Privacy page**: yes (recommended), and your contact email to show on it, if any.
6. Whether the keep-warm uptime ping is OK.
