# Phase 7 — Coding platform (plan, for approval)

Status: **DRAFT 2026-10-03, awaiting the owner's approval.** Nothing below is built yet.
Owner decisions so far: free tier only; languages **C++, Python, JavaScript**.

## 1. What it is for

The editor appears only in the three interview types that have a coding round: **Coding** (two 25-min problems), **Web Dev** (two 25-min problems) and **SDE** (one 20-min block). The other five types stay talk-only.

Flow: the AI interviewer states a problem from the question bank -> the candidate writes code beside the chat -> **Run** tests it on the visible sample cases -> **Submit** runs all cases (visible and hidden) and gives pass/fail -> the interviewer reads the code and results and asks follow-ups -> Phase 9 reports use the results as evidence.

## 2. The key decision: where code runs (free tier)

| Language | Where it runs | Cost / limit |
|---|---|---|
| **Python** | In the candidate's browser (Pyodide, WebAssembly, in a Web Worker) | free, unlimited |
| **JavaScript** | In the browser (sandboxed Web Worker, killed after 5 s) | free, unlimited |
| **C++** | On the server side through Judge0's free plan | **rationed**; limit unknown until the owner checks the plan |

`ExecutionBackend` is an interface (plan decision D11): a `BrowserBackend` (the page does the work and reports back) and a `Judge0Backend`. A paid or self-hosted Judge0 can replace the free one later with a config change.

### Honest trade-offs of running Python/JS in the browser
1. **Hidden test cases reach the browser** (they must, to be run there). A determined user can read them in dev tools. For a personal practice tool this only spoils your own practice, so it is accepted; it is *not* acceptable if results ever become a credential for others.
2. **Browser results are self-reported**: the page tells the server "7/8 passed". A user could fake that. Same reasoning: it only affects the user's own practice and the interviewer's feedback. C++ results come from the server and are trustworthy.
3. First load of Pyodide is ~10 MB (cached afterwards), so Python needs a "Loading Python..." state.

These are written into `docs/FACTS.md` as known limits, not hidden.

## 3. Steps

**7.1 Execution layer (backend)** — `app/execution/`: `ExecutionBackend` protocol (`run(language, source, stdin) -> Result`, `run_batch`), `Judge0Backend` (httpx; `wait=false` + batch + polling; base64 payloads; limits: 2 s CPU, 128 MB, 64 KB source, 64 KB stdin; API URL/key/host header from env so RapidAPI or Judge0's own host both work), typed errors (rate-limited, unavailable, timeout) mapped into the existing error envelope, per-user daily cap and a global cap (env-configurable; default **40 C++ executions/user/day**, counted per execution so a Submit of 8 cases costs 8) with a clear "N runs left today" message.

**7.2 Data (migration `0026_coding`, needs go-ahead)** — `code_submissions` (interview_id, user_id, question_id, language, source, kind run|submit, passed, total, public_results jsonb, source_of_result browser|judge0, created_at), cascade-deleted with the interview, RLS on with no client access (backend only), index on (interview_id, created_at). Hidden-case details (input/expected) are never stored in results, only pass/fail and counts.

**7.3 API** — `GET /interviews/{id}/problem` (current question, visible cases, languages, remaining C++ executions; hidden cases only on Submit for browser languages), `POST /interviews/{id}/run` and `/submit` (C++: runs as a `code_run` job through the M4 job runner, polled; Python/JS: the browser reports results to `POST /interviews/{id}/submissions`), owner and phase checks (only while a problem phase is active and the interview is in progress), per-user throttle.

**7.4 Frontend** — Monaco editor (`@monaco-editor/react`, lazy-loaded) beside the transcript; language picker with per-language starter code; Run / Submit; output + per-case results panel (hidden cases shown only as "hidden case 3: passed/failed"); Web Workers for Python (Pyodide from a CDN, lazy) and JavaScript (stdin shim + captured console output, 5 s kill); polling UI for C++ jobs reusing the M4 pattern; keyboard/a11y basics.

**7.5 Interviewer awareness** — the latest code snapshot and last result summary go into the turn prompt as **untrusted data blocks** (delimited, sanitized, capped at ~1,500 tokens, only when changed since the last turn), so the interviewer can discuss the code and cannot be instructed by it (injection corpus extended with "ignore previous instructions" inside code comments). Leak filter stays on.

**7.6 Question bank** — standard case format `{"input": str, "expected_output": str, "hidden": bool}` validated server-side (size caps, at least one visible and one hidden case), admin form gets a simple case editor instead of raw JSON; a small starter set of problems provided as JSON for the admin to load (embedding happens when the admin saves, using their key).

**7.7 Tests** — fake Judge0 (recorded response shapes), cap and throttle enforcement, hidden-case masking, phase/ownership checks, job lifecycle for C++, injection corpus for code, frontend `tsc`/`eslint`/`next build`. Live checks the owner runs: one C++ hello-world through the real Judge0 account and one Python run in the browser.

## 4. What I need from the owner

1. Approve this plan (or change it).
2. Accept the browser-run trade-offs in section 2 (hidden cases visible, results self-reported for Python/JS).
3. Before the **live** C++ test (not before building): create the Judge0 free-plan account, tell me the daily limit and whether it required a card, and put `JUDGE0_API_URL`, `JUDGE0_API_KEY` (and host header if RapidAPI) in `apps/api/.env`.
4. Go-ahead for migration `0026_coding` when it is written.

## 5. Risks

- Free-plan limit unknown -> the cap is a config value; the design works at any limit.
- Pyodide/Monaco bundle weight -> both lazy-loaded, only on the interview page when a coding phase starts.
- A free shared service can be down or throttled -> typed errors and a clear message; Python/JS keep working.
- Web Dev interviews: only JavaScript problems for now (HTML/CSS live preview is out of scope).
