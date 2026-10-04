# CyntraAI launch checklist

Status: **DRAFT FOR APPROVAL, written 2026-10-04.** Tick each box yourself; the assistant cannot do the dashboard or account steps. Order matters where stated. The deployment steps are in `docs/DEPLOY.md`; the reasons behind most items are in `docs/audit/*.md` (finding ids in brackets).

Nothing on this list has been done yet. As of 2026-10-04 only these paths have run against the live stack: sign-in/roles, the BYOK Gemini key, chat, resume upload + processing, and one ATS check. Everything else has been tested with mocks only, so section 7 (the walk-through) is where most of the real verification happens.

## 1. Repository and CI
- [ ] Create a **private** GitHub repository and push `main` (the project has no git remote today: it exists on one laptop only) [M-02].
- [ ] Make sure CI is green on the first run. At HEAD the web job's `npx tsc --noEmit` fails on a clean checkout because Next's generated `LayoutProps` type is gitignored [H-02]. An uncommitted change adds `npx next typegen` before it; that the command produces the types on a clean runner is **unverified** until CI runs.
- [ ] Add `.gitattributes` (`* text=auto eol=lf`) and `.claude/settings.local.json` to `.gitignore` [L-10, L-11].
- [ ] Confirm no `.env*` file is tracked (`git ls-files | grep env` shows only `apps/api/.env.example`). The audit found no secret in the tree or in history on 2026-10-04.

## 2. Secrets: rotate everything that was shared
Credentials were pasted into chat sessions during development (recorded in the documentary). Treat all of them as exposed.
- [ ] **Supabase service-role key**: rotate (Project Settings > API), update `apps/api/.env`, then Render.
- [ ] **Supabase JWT secret** (the legacy HS256 secret) if it was shared: rotate or revoke; confirm the API still verifies sign-ins (ES256 via JWKS is the main path). Whether the legacy secret is still active is **unverified** (audit 12.5).
- [ ] **Supabase S3 access key** (Storage): delete the old key, create a new one, update Render **and** Vercel.
- [ ] **Your own Gemini key** (and any Groq/Claude key you shared): revoke and re-create in the provider's console; re-enter it in the app's Settings > API Keys.
- [ ] **`KEY_ENCRYPTION_SECRET`**: if it was ever shared, rotate without losing saved keys: generate a new Fernet key, set `KEY_ENCRYPTION_SECRET=<new>,<old>`, restart, run `python -m scripts.rotate_keys` (dry run) then `--apply` (from `apps/api`), then remove `<old>` and restart. Never generate a brand-new key and drop the old one: every stored user API key would become unreadable.
- [ ] Re-enter all new values only in Render and Vercel (and your local `.env` files). Never paste them into chat or commit them.

## 3. Remove the temporary sign-up and tighten Supabase Auth
- [ ] **Demo sign-up**: remove `apps/web/app/(auth)/sign-up/` and its link in the sign-in page, **or** rely on the gate in `apps/web/lib/demo-signup.ts` (off in production builds unless `NEXT_PUBLIC_ENABLE_DEMO_SIGNUP=true` at build time; leave it unset). That gate is an **uncommitted** working-tree change at the time of writing and was not verified; at HEAD the page is in the production build and anyone can reach it [M-2, M-08]. After deploying, open `/sign-up` on the live site and confirm it is gone. Also: on an empty database the first account to sign in becomes the Owner, so sign in yourself first.
- [ ] Supabase > Authentication: **disable email sign-ups** (keep Google); decide on "confirm email". Whether they are enabled today is **unverified** (not visible from SQL).
- [ ] Supabase > Authentication: turn on **leaked-password protection** (security advisor WARN; may need a paid plan, unverified) [advisor `auth_leaked_password_protection`].
- [ ] Re-run Supabase advisors (security first) after any migration: expect only the four intentional "RLS enabled, no policy" notices (`ats_scores`, `code_submissions`, `interview_reports`, `jobs`).

## 4. Database hardening (needs your explicit go-ahead per migration)
- [ ] Review and decide on the hardening migration (a draft `apps/api/migrations/0030_final_hardening.sql` was in the working tree on 2026-10-04): revoke browser write privileges on tables the web app never writes (`chat_messages`, `resume_chunks`, `llm_usage`, `roles`, `admin_permissions`, narrow `conversations`/`notifications`/`profiles`), drop the duplicate `admin_permissions` unique constraint and three redundant indexes, make the two NO-ACTION foreign keys `ON DELETE SET NULL` (otherwise deleting a user who granted permissions or created questions fails), index `code_submissions.user_id/question_id`, drop the dead `question_bank_select_all` policy [H-01, M-01, L-01 to L-05]. Without this, any signed-in account can fill the free 500 MB database with its own token.
- [ ] After applying, verify against the live catalog (grants per table, advisors) and re-run the test suite.
- [ ] Optional but recommended once: replay migrations 0001-0029 in numeric order on a throw-away Supabase project and diff the catalog with production [M-03].

## 5. Quality scripts and data (owner-run, on your machine, with your own key)
Set the key in the shell (`$env:GEMINI_API_KEY="..."` in PowerShell), work from `apps/api` with the venv active. The assistant never runs these. In this order:
- [ ] `python -m scripts.load_starter_questions` (dry run) then `--apply`: loads 3 starter coding problems with reference solutions (1 embedding request). **The question bank is empty today**, so Coding, Web Dev and SDE interviews have nothing to ask until this is run [M-07]. Three problems are not enough: Web Dev needs 2 per interview and SDE 1, and the starter set has 2 coding + 1 web-dev + 0 SDE, so add more through the question-bank page (the audit suggests at least 6 coding, 4 web-dev, 3 SDE) [BE-H1].
- [ ] `python -m scripts.llm_smoke --record` (about 10 Gemini requests, spaced): records real error bodies, thinking behaviour and latency into `tests/fixtures/gemini/` (which makes the currently skipped `test_recorded_fixtures` run). Add `--groq --claude` with `GROQ_API_KEY` / `ANTHROPIC_API_KEY` if you have those keys. Note the results in `docs/FACTS.md` (is `thinkingLevel: minimal` accepted? real 429 bodies?).
- [ ] Pin the Gemini model id in `apps/api/app/llm/models.py` once the smoke run shows which model to trust (it is the moving alias `gemini-flash-lite-latest` today) [M-05].
- [ ] `python -m scripts.rag_eval_live` (8 embedding requests): set the ATS calibration constants `LOW` and `HIGH` in `apps/api/app/ats/semantic.py` (placeholders 0.55 / 0.80 today; the semantic score is 40% of the ATS composite).
- [ ] `python -m scripts.judge_eval_live` (12 requests): record the code-review agreement figure.
- [ ] `python -m scripts.report_eval_live` (4 requests): confirm scores order strong > average > weak and the injection candidate stays low.
- [ ] Record all results in `docs/FACTS.md` and commit the new fixtures.

## 6. Production configuration and hosting
- [ ] Follow `docs/DEPLOY.md` (Supabase, Vercel, Render, in the order given there).
- [ ] Render: `ENVIRONMENT=production`, `CORS_ORIGINS` = the exact Vercel origin (no localhost), exactly one instance and one worker; `/docs` and `/openapi.json` return 404 [L-12].
- [ ] Supabase Auth Site URL and Redirect URLs point at the Vercel URL.
- [ ] **Security headers** on the web app (`next.config.ts` has none at HEAD; an uncommitted change adds `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, a `Permissions-Policy` allowing the microphone for this origin, and a conservative `Content-Security-Policy` without script/style/connect rules). A strict script/connect CSP would have to allow your Supabase and API origins and the Monaco CDN (or self-host Monaco) [FE M-1, M-14]. Check the live headers with `curl -I https://<vercel-url>/sign-in`.
- [ ] **Privacy page** (`/privacy`): add a real contact address (it currently says "contact the site owner" with no address) and one line about the Monaco editor files loading from a third-party CDN [FE L-14].
- [ ] **Dependencies**: upgrade the pinned Python packages that carry advisories (fastapi/starlette, cryptography, pdfplumber/pdfminer.six, python-jose or move to PyJWT; an uncommitted change already raises several pins), `npm audit fix` and Next 16.3.8, then re-run the whole suite and `llm_smoke` [M-10].
- [ ] **Backups**: the live database holds your users' keys and data. Take a manual export before launch and before each migration; whether the free plan includes automatic backups or point-in-time recovery is **unverified**. Know that Storage objects are not part of a database export.
- [ ] **Monitoring**: free uptime monitor on `https://<render-url>/ready` (alerts on 503, which also means a paused Supabase project, and keeps Render warm); watch the Supabase dashboards (database size against 500 MB, storage against 1 GB, project not paused) [M-06].
- [ ] Gemini quota: remind testers that each user's Gemini quota is per Google project; a backup key only helps if it comes from a different project.

## 7. Final manual end-to-end walk-through (on the deployed site, two accounts)
Use a private window. Account A is the Owner (sign in first); account B is a normal user (a second Google account). Tick when the behaviour is right, and write down anything odd.

**Accounts and roles**
- [ ] A: Google sign-in, account setup (set a password), onboarding, add a Gemini key; the dashboard loads. A sees Team and Question Bank links; B does not.
- [ ] Sign out and back in; protected pages redirect to sign-in when signed out; `/privacy` opens signed out.
- [ ] Settings > API Keys: key list, "Used today" shows numbers after some use; deleting a key asks for confirmation (and warns for a Gemini primary).
- [ ] Add a Groq or Claude key if you have one, and confirm it validates; try an invalid key and see a clear error and nothing stored.
- [ ] A: Team page lists users; promote B to Admin, grant and revoke `manage_question_bank`, demote B (asks for confirmation); the Owner row cannot be changed. B then does or does not see the Question Bank link accordingly.

**Chat**
- [ ] New chat, streamed reply, copy, provider selector shows only providers with valid keys, rename, delete (confirmation), "show older" if applicable.

**Resumes**
- [ ] Upload a PDF and a DOCX under 500 KB; rejected: a larger file, a wrong type. Processing completes; rename a resume; a 4th upload is refused with the limit message; Retry processing works; delete asks for confirmation and removes it (check the Storage object disappears).
- [ ] B cannot see A's resumes (open B's resume list; try A's resume id URL if you can).

**ATS**
- [ ] Run an ATS check with a real JD: score, three sub-scores, requirements checklist with evidence, feedback. Run 2-3 checks; "Previous checks" lists them (at most 10 per resume), open one (banner), delete one.

**Interviews**
- [ ] Load the question bank first (section 5). Question Bank page: add, edit (including clearing topic/difficulty), delete; reference solution is entered here and never shown to candidates.
- [ ] Start a **Behavioral** interview: the setup screen shows progress, then the room opens; answer by typing; timer and phase update; end the interview.
- [ ] Start a **Coding** interview: the Monaco editor appears in problem phases; discuss, write code, press Submit (confirmation), wait for the review, see the interviewer's reaction; a second submit for the same problem is refused; the editor closes outside problem phases. Repeat once in **Web Dev** and **SDE** to check there are enough questions in the bank.
- [ ] Try the other types at least once briefly: HR, ML/AI, System Design, Case Study.
- [ ] **Voice** in Chrome or Edge: allow the microphone, turn voice on mid-interview, answer out loud, edit-before-send, silence nudge at about 20 s, "Stop speaking", interruption option with headphones, deny the microphone and confirm typing still works. Note the four known voice bugs (turning voice on mid-interview may not read the pending question; the closing message may be cut off; mic error latches until reload; speaking race) [FE M-3 to M-6]. Check Firefox falls back to typing.
- [ ] Cancel an interview while it is setting up; delete a finished interview.
- [ ] Let one interview run to its time limit or end it manually; confirm it shows as completed.

**Reports**
- [ ] On a completed interview (3 or more answers) press Get my report: progress, then the report with scores, quotes, code verdicts and a "days left" countdown; print to PDF (also try dark theme: printing may show dark panels [FE M-11]); text/Markdown export; delete the report.
- [ ] Confirm the expiry rule on a test report if you can wait or backdate `expires_at` in the database (7 days; refused with "expired").

**Platform behaviour**
- [ ] After Render sleeps (15 minutes idle), open the app: the "Waking the server..." banner appears and the app recovers.
- [ ] Notifications bell: trigger a failover (primary key deliberately exhausted or invalid with a valid backup) and check the notice appears.
- [ ] Light and dark themes, a phone-width window (375 px), keyboard-only navigation of the main flows.
- [ ] Browser console and Render logs show no unexpected errors during the walk-through.

## 8. Go / no-go
- [ ] Sections 1-6 complete; section 7 complete with no blocking issue.
- [ ] Open items accepted and written down: single worker and cold starts, voice bugs if not yet fixed, free-tier limits, unmeasured model behaviour for Claude and Groq, no automated backups (unverified), no real-Postgres CI tests, no Playwright smoke test.
