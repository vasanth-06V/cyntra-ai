# Frontend audit (apps/web), final whole-project pass

Auditor: frontend partition. Date: 2026-10-04. Scope: everything in `apps/web` except `node_modules` and `.next`. Method: every source file was read in full (no sampling), the other side of every API call was read in `apps/api` (routers, pydantic models, services, migrations), and `tsc`, `eslint`, `vitest`, `next build`, `npm audit`, `npm ls` were run. The dev server was started only to look at `/sign-in`, `/privacy` and the signed-out redirect of `/dashboard`, then stopped. No file other than this report was written; `git status` is clean.

Note on `.env.local`: the instructions said never to read it. One of my batch commands listed it (`cat`/`sed` over a file list) and was blocked by the permission layer before any output; no value was seen or printed.

## 1. Summary and exact tool results

| Check | Result |
|---|---|
| `npx tsc --noEmit` | exit 0, no errors |
| `npx eslint .` | exit 0, no warnings (config: `eslint-config-next` core-web-vitals + typescript; 2 inline disables, both justified) |
| `npx vitest run` | 24 files passed, **158 tests passed**, 0 failed, duration 69 s |
| `npx next build` (Next 16.3.7, Turbopack) | success; 21 static/dynamic pages generated; `/privacy`, `/sign-up`, `/_not-found` static, everything else dynamic; "Proxy (Middleware)" registered |
| `npm audit` (all) | 9 vulnerabilities: 2 low, 2 moderate, 5 high. **All dev-time or transitive** except the 2 low |
| `npm audit --omit=dev` | 2 low: `dompurify 3.4.13-3.4.15` (DOM XSS in IN_PLACE hook) via `monaco-editor`. The app never calls DOMPurify directly; fix is `npm audit fix` (non-breaking) |
| dev-only highs | `braces` (ReDoS-style stack exhaustion) via `eslint-config-next -> @next/eslint-plugin-next -> fast-glob -> micromatch`; `@vitest/mocker` moderate (path traversal in redirect mocks). Fixes are `--force` major downgrades/upgrades; not worth it |
| Unused dependencies | `zod`, `zustand`, `@react-three/drei` are never imported. `three` is only a type import (needed as peer of `@react-three/fiber`). `@supabase/supabase-js` is only a peer of `@supabase/ssr` (fine). `npm ls` also shows 6 "extraneous" wasm packages (harmless) |
| Line endings / encoding | all source LF, ASCII/UTF-8; no CRLF files |
| Bundle (build output, gz) | largest chunk 916 KB raw / **241 KB gz = three.js** (lazy, only loaded on the interview-setup wait screen); Supabase client chunk 258 KB raw / 67 KB gz in the shared bundle; Monaco is not in the bundle (loaded from a CDN at runtime, see F-M14) |

Files: 163 files in the partition (145 `.ts/.tsx`, of which 24 are tests; plus css, json, mjs, ico, 5 svg, md). All accounted for in section 2. Dead/orphan code found: 1 whole component file, 2 icons, 1 type, 5 public svgs, 3 unused npm deps.

Overall verdict: the web app is in good shape. **No CRITICAL and no HIGH finding survived verification.** Every API call matches its backend route, method, body and response model; every link/redirect target resolves; no `window.confirm/alert/prompt`, no `dangerouslySetInnerHTML`, no `any`, no leftover `console.log`/TODO. The real problems are concentrated in (a) the browser-voice layer (four confirmed bugs, MEDIUM), (b) missing HTTP security headers and a shipped "DO NOT SHIP" demo sign-up route, (c) a few async/edge cases, and (d) test gaps around the API client, `useVoice`, and the auth/guard layer.

## 2. Complete file table

Legend for "tests": file names are the test files that exercise it (directly or through a parent). "NONE" means no test touches it. Issue IDs refer to section 4.

### 2.1 Config and root

| Path | Purpose | Used by | Test | Issues |
|---|---|---|---|---|
| package.json | deps/scripts | npm | n/a | L-24 (unused deps) |
| package-lock.json | lockfile (10,287 lines) | npm/CI | n/a | L-25 (audit) |
| tsconfig.json | strict TS, `@/*` alias | tsc/next | n/a | none |
| eslint.config.mjs | next core-web-vitals + ts | eslint/CI | n/a | none |
| vitest.config.ts | node env default, jsdom per file, setup file | vitest | n/a | none |
| postcss.config.mjs | tailwind v4 plugin | next | n/a | none |
| next.config.ts | empty config | next | n/a | **M-1** (no security headers) |
| next-env.d.ts | generated | tsc | n/a | none |
| proxy.ts | Supabase session refresh on every request (`proxy` export, matcher excludes static) | Next | NONE | P-1 (one auth network call per request) |
| .gitignore | ignores `.env*` | git | n/a | L-35 (no .env.example) |
| AGENTS.md / CLAUDE.md | Next-16 warning (auto-generated) | agents | n/a | none |
| README.md | create-next-app boilerplate | humans | n/a | L-24 (stale boilerplate) |
| .env.local | secrets | Next | not read | none |

### 2.2 app/ (routes)

| Path | Purpose | Linked from | Test | Issues |
|---|---|---|---|---|
| app/layout.tsx | root: fonts, Theme/Motion/Toast/Confirm providers | all | indirect (test/utils mirrors it) | L-19 (single static title) |
| app/page.tsx | `/` redirect to /dashboard or /sign-in | Logo links, guards | NONE | none |
| app/globals.css | tokens, animations, print, reduced motion (432 lines) | layout | NONE | M-10, M-11, L-24 (unused tokens) |
| app/favicon.ico | favicon | browser | n/a | none |
| app/privacy/page.tsx | static privacy page | footer, AuthShell | NONE (looked at live: renders, no console errors) | L-14 (does not mention Monaco CDN) |
| app/auth/callback/route.ts | OAuth code exchange then redirect | Supabase/Google | NONE | none |
| app/(auth)/sign-in/page.tsx + SignInView.tsx | Google + email sign-in | redirects, sign-out | NONE | L-36, L-37 |
| app/(auth)/sign-up/page.tsx + DemoSignUpView.tsx | temporary email sign-up | sign-in link | NONE | **M-2** |
| app/(auth)/account-setup/page.tsx + AccountSetupForm.tsx | password + profiles row | guards | NONE | M-13 |
| app/(auth)/onboarding/page.tsx + OnboardingFlow.tsx | Gemini key then optional keys | guards, setup | NONE (ProviderKeySection tested) | L-8 (no retry-less error) |
| app/(dashboard)/layout.tsx | re-exports DashboardShell | Next | NONE | P-1 |
| app/(dashboard)/DashboardShell.tsx | sidebar, header, bell, theme, sign-out, footer, skip link | all dashboard pages | NONE | M-7, P-1 |
| app/(dashboard)/template.tsx | fade-in on every navigation (CSS) | Next | NONE | none |
| app/(dashboard)/dashboard/{page,DashboardHome}.tsx | landing, 3 steps, 3 features | sidebar | NONE | P-1 |
| app/(dashboard)/chat/{page,ChatListView}.tsx | conversation list, new, rename, delete, older | sidebar | ChatListView.test, ChatRename.test | none |
| app/(dashboard)/chat/[conversationId]/{page,ChatThreadView}.tsx | thread header, rename, ChatWindow | chat list | ChatRename.test (ChatWindow mocked) | L-18 |
| app/(dashboard)/interviews/{page,InterviewsView}.tsx | list, delete, older | sidebar | InterviewsView.test | M-12 |
| app/(dashboard)/interviews/setup/{page,InterviewSetupView}.tsx | setup form, job polling, cancel | interviews list, dashboard | InterviewSetupView.test (cancel only) | L-33, L-34 |
| app/(dashboard)/interviews/[interviewId]/{page,InterviewRoomView}.tsx | room: chat, voice, editor, end/cancel/delete | list, setup | InterviewRoomView.test, InterviewRoomActions.test (voice+editor mocked) | **M-3, M-4**, L-16, L-20, L-26, L-27 |
| app/(dashboard)/ats-score/{page,AtsScoreView}.tsx | score form, result, history | sidebar | AtsScoreView.test, AtsHistory.test (ScoreBreakdown mocked) | M-10 |
| app/(dashboard)/resumes/{page,ResumesView}.tsx | upload, rename, retry, delete, 3 limit | sidebar | ResumesView.test | L-29 |
| app/(dashboard)/reports/{page,ReportsView}.tsx | reports list, generate | sidebar | Reports.test (generation untested) | L-28 |
| app/(dashboard)/reports/[interviewId]/{page,ReportDetailView}.tsx | report detail, print, download, delete | list | Reports.test | M-11, L-21 |
| app/(dashboard)/settings/api-keys/{page,ApiKeysView}.tsx | keys + usage | sidebar | ProviderKeySection.test (view itself NONE) | L-30 |
| app/(dashboard)/settings/team/{page,TeamView,TeamManager}.tsx | owner-only roles/permissions | sidebar (owner) | TeamManager.test (guard NONE) | none |
| app/(dashboard)/admin/question-bank/{page,QuestionBankView}.tsx | question CRUD | sidebar (owner/perm) | QuestionBankView.test, QuestionBankClear.test | none |
| app/api/resumes/route.ts | GET list, POST upload (+trigger processing) | ResumesView, fetchResumes | resumes.route.test | M-8 |
| app/api/resumes/[id]/route.ts | DELETE, PATCH rename | ResumesView | resumes.route.test | none |
| app/api/resumes/resumes.route.test.ts | 18 route-handler tests | vitest | n/a | processing-fetch path untested |
| other *.test.tsx in app/ (12 files) | see section 6 | vitest | n/a | none |

### 2.3 components/

| Path | Purpose | Imported by | Test | Issues |
|---|---|---|---|---|
| ats/AtsHistoryPanel.tsx | last-10 history list, open/delete | AtsScoreView | AtsHistory.test | none |
| ats/ScoreBreakdown.tsx | composite ring, sub-scores, tips, coverage | AtsScoreView | **NONE (mocked in both ATS tests)** | none |
| chat/ChatWindow.tsx | message log, provider select, streaming send | ChatThreadView | ChatWindow.test | L-18, L-22, L-39 |
| chat/MessageBubble.tsx | bubble (text only), copy | ChatWindow, InterviewRoomView | ChatWindow.test | `TypingDots` export used only internally |
| interview/CodeEditorPanel.tsx | Monaco, language, submit/confirm, review polling, draft | InterviewRoomView | CodeEditorPanel.test (4 tests, Monaco faked) | M-14, L-17, L-32, L-34 |
| interview/PhaseTimer.tsx | phase + countdown | InterviewRoomView | NONE | none |
| interview/VoiceBar.tsx | voice on/off, caption edit, settings | InterviewRoomView | **NONE (useVoice mocked in room tests)** | **M-6** (never calls clearError), L-31 |
| settings/ProviderKeyForm.tsx | save/replace/delete one key | ProviderKeySection | ProviderKeySection.test | L-30 |
| settings/ProviderKeySection.tsx | card per provider, backup slot | ApiKeysView, OnboardingFlow | ProviderKeySection.test | L-30 |
| settings/UsageToday.tsx | today's usage | ApiKeysView | NONE | none |
| three/LoadingScene.tsx, .inner.tsx, scenes/RotatingIcosahedron.tsx | lazy 3D loader, reduced-motion aware | InterviewSetupView | NONE (mocked) | none |
| ui/Alert, Badge, Button, Card, EmptyState, LinkButton, ListRow, Logo, PageHeader, ProgressBar, ScoreRing, Skeleton, Spinner, AuthShell, CountUp | presentation primitives | many | indirect | `Logo` has `useId` without "use client" (works: server components may call useId) |
| ui/ConfirmDialog.tsx, ConfirmProvider.tsx | in-app confirm (alertdialog, focus trap, restore focus) | all destructive flows | ConfirmDialog.test | none |
| ui/Toast.tsx | polite/assertive regions | all | Toast.test | none |
| ui/InlineRename.tsx | inline rename (Enter/Esc, validation) | chat list/thread, resumes | ChatRename.test, ResumesView.test | none |
| ui/NavLinks.tsx | active-link nav (aria-current) | DashboardShell | NONE | none |
| ui/NotificationsBell.tsx | Supabase notifications, 60 s poll | DashboardShell | NotificationsBell.test | L-23, L-38 |
| ui/ServerWakingBanner.tsx | banner while API retried | DashboardShell | NONE | L-22 |
| ui/SignOutButton.tsx, ThemeToggle.tsx | sign out, theme + view transition | shell/AuthShell | NONE | none |
| ui/StubPage.tsx | **ORPHAN** "not available yet" page | nothing | NONE | L-24 |
| ui/button-styles.ts, score.ts | shared class/tone maps | Button/LinkButton; score users | indirect | none |
| ui/icons.tsx | icon set (223 lines) | many | n/a | `HomeIcon`, `InboxIcon` unused (L-24) |

### 2.4 lib/, types/, test/, public/

| Path | Purpose | Imported by | Test | Issues |
|---|---|---|---|---|
| lib/api-client/fastapi.ts | bearer fetch, retry GET on 502/503/504/network, 90 s/30 s timeouts, error envelope, 401 redirect, `streamPost` | ~20 views | **NONE (always mocked)** | L-9, L-22 |
| lib/api-client/server-status.ts | waking store | fastapi, banner | NONE | L-22 |
| lib/auth/guards.ts | requireUser/Role/Permission | shell, pages | **NONE** | **M-7**, P-1 |
| lib/supabase/client.ts, server.ts | ssr clients (anon key only) | views, guards | n/a | none |
| lib/storage.ts | S3 upload/delete, `server-only` | api/resumes routes only | mocked | none (not importable by client) |
| lib/resumes.ts | limits, validation, `fetchResumes` | resume/ATS/setup views, route | resumes.test | `MAX_RESUME_BYTES`, `RESUME_EXTENSIONS` exported but only internal |
| lib/format.ts | relativeTime, formatDateTime, initials | several | format.test | none |
| lib/chat.ts, lib/team.ts | title validation; permission list | chat views, TeamManager | format.test; TeamManager.test | none |
| lib/ats/feedback.ts | parse model feedback into bullets | ScoreBreakdown | voice.test (misplaced) | none |
| lib/reports/format.ts | labels, timeLeft, markdown | report views | reports.test | none |
| lib/reports/useReportGeneration.ts | start + poll report job (5 min) | ReportsView | **NONE** | L-34 |
| lib/theme/ThemeProvider.tsx, MotionProvider.tsx | next-themes, MotionConfig reducedMotion="user" | layout | n/a | none |
| lib/voice/endpointing.ts, speech-text.ts, settings.ts, recognizer.ts (mapper only) | pure logic | useVoice | voice.test | none |
| lib/voice/synthesizer.ts | SpeechSynthesis wrapper | useVoice, VoiceBar | NONE | **M-5** |
| lib/voice/useVoice.ts | recognizer + TTS + nudges state machine | InterviewRoomView | **NONE (mocked in room tests)** | **M-3, M-4, M-5, M-6**, L-31 |
| types/{ats,chat,coding,interviews,jobs,keys,reports,resumes,team}.ts | API shapes | views | n/a | `ScoreRequest` unused; verified against backend (section 3) |
| test/setup.ts, utils.tsx, vitest.d.ts | jsdom helpers, providers, fetch mock | tests | n/a | none |
| public/{file,globe,next,vercel,window}.svg | create-next-app leftovers, referenced nowhere | nothing | n/a | L-24 |

## 3. Route map and API contract matrix

### 3.1 Route map (21 pages + 3 handlers)

| Route | Type | Guard | Reachable from |
|---|---|---|---|
| `/` | redirect | none (user ? /dashboard : /sign-in) | logos |
| `/sign-in` | public | none (does not redirect signed-in users, L-36) | guards, sign-out, 401 handler |
| `/sign-up` | public (demo) | none | link on sign-in (M-2) |
| `/auth/callback` | GET handler | code exchange; to /dashboard, /account-setup or /sign-in?error | Google |
| `/account-setup` | page | custom: user required, redirects to /dashboard if profile exists | guards, callback |
| `/onboarding` | page | custom: user + profile required | guards, account-setup |
| `/privacy` | public static | none | footers |
| `/dashboard`, `/chat`, `/chat/[id]`, `/interviews`, `/interviews/setup`, `/interviews/[id]`, `/ats-score`, `/resumes`, `/reports`, `/reports/[id]`, `/settings/api-keys` | pages | layout `requireUser` (and DashboardHome again) | sidebar/mobile bar/dashboard cards |
| `/settings/team` | page | `requireRole("owner")` in page | sidebar (owner only) |
| `/admin/question-bank` | page | `requirePermission("manage_question_bank")` in page | sidebar (owner or permission) |
| `/api/resumes` GET/POST, `/api/resumes/[id]` DELETE/PATCH | handlers | `auth.getUser()` + `user_id` scoping in each | ResumesView, `fetchResumes` |

Verdicts:
- **Link/redirect resolution: PASS.** Every `href`, `router.push`, `redirect()` and `location.assign` target (full list grepped) matches a real route. No orphan pages (`/sign-up` is reachable only from a dev link, `/interviews/setup` from the list, dashboard and empty state).
- **Nav items: PASS.** 6 base + Team (owner) + Question Bank (owner or permission), same list rendered as sidebar and as mobile bar; active state via `aria-current`. Hidden items are re-checked server-side in the pages.
- **Guards: PASS with caveats.** The dashboard layout guards hard loads; client-side navigations do not re-run the layout, so Team and Question Bank guard in the page itself (correct per the `requirePermission` comment) and the backend re-checks every call. Caveat M-7: guards ignore query errors.
- **Redirects after auth:** Google -> callback -> /dashboard or /account-setup; email sign-in -> /dashboard (then guard chain); account-setup -> /onboarding; onboarding "Finish" -> /dashboard; sign-out -> /sign-in; 401 -> hard `/sign-in`. All consistent.
- **Next 16 specifics checked against `node_modules/next/dist/docs`:** `proxy.ts` with named `proxy` export and matcher is the documented convention; `params`/`searchParams` are awaited promises; `LayoutProps<"/">` is the generated global helper; dynamic page re-exports of client components build fine.
- **No `error.tsx`, `not-found.tsx`, `loading.tsx` anywhere** (L-15): any thrown server error falls to the default Next error screen.

### 3.2 API contract matrix (frontend call -> backend route -> verdict)

All backend paths read from `apps/api/app/*/router.py`; models from `*/models.py`/`schemas.py`. Base URL = `NEXT_PUBLIC_API_URL`.

| Frontend caller | Call | Request body | Backend | Verdict |
|---|---|---|---|---|
| OnboardingFlow, ApiKeysView, ChatThreadView, AtsScoreView, InterviewSetupView | GET `/keys` | none | `ProviderKeyOut[]` (id, provider, slot, is_valid, last_validated_at) | OK, matches `types/keys.ts` |
| ProviderKeyForm | POST `/keys` | `{provider, slot, api_key}` | 201 `ProviderKeyOut`; `api_key` 8..512 (UI checks >= 8, maxLength 512) | OK |
| ProviderKeyForm | DELETE `/keys/{id}` | none | 204 | OK |
| UsageToday | GET `/usage` | none | list of {provider, kind, requests, input_tokens, output_tokens, thought_tokens} | OK |
| ChatListView | GET `/chat/conversations[?limit&offset]` | none | `ConversationOut[]`, page size 50 default, max 200 | OK |
| ChatListView | POST `/chat/conversations` | `{}` | 201 `ConversationOut` | OK |
| ChatListView, ChatThreadView | PATCH `/chat/conversations/{id}` | `{title}` | `title` 1..120, UI validates same | OK |
| ChatListView | DELETE on Supabase `conversations` (direct) | n/a | policy `conversations_owner_only` for all; `.select("id")` verifies a row was deleted | OK |
| ChatThreadView | Supabase `conversations.select("title")` | n/a | owner RLS | OK |
| ChatThreadView | GET `/chat/conversations/{id}/messages` | none | latest 200 messages, oldest first (`ChatMessageOut`) | OK, but no way to see older than 200 (L-18) |
| ChatWindow | POST (stream) `/chat/conversations/{id}/messages` | `{provider, content}` | `content` 1..8000 (UI maxLength 8000); text/plain stream; first chunk pulled before 200 so errors are JSON | OK |
| InterviewsView, ReportsView | GET `/interviews[?limit&offset]` | none | `InterviewOut[]` | OK matches `types/interviews.ts` |
| InterviewSetupView | POST `/interviews` | `{type, provider, resume_id, jd_text}` | 202 `{job_id, interview_id}`; jd 10..20000; provider gemini/groq only (UI filters) | OK |
| InterviewSetupView, CodeEditorPanel, useReportGeneration | GET `/jobs/{id}` | none | `JobOut` {id, kind, status, progress, result, error{code,message,status}, subject_id, created_at} | OK matches `types/jobs.ts` |
| InterviewSetupView, InterviewRoomView | POST `/interviews/{id}/abort` | none | `InterviewOut`; code `interview_not_cancellable` (409) exists in `interviews/service.py:493` | OK |
| InterviewRoomView | GET `/interviews/{id}`, `/transcript` | none | `InterviewOut`, `TranscriptEntryOut[]` | OK |
| InterviewRoomView | POST `/interviews/{id}/turns` | `{content}` | `content` 1..4000 (UI 4000); `TurnResponse` {message, phase, minutes_remaining, is_final_phase}; 409 code `interview_ended` exists | OK |
| InterviewRoomView | POST `/interviews/{id}/complete` | none | `InterviewOut` (UI ignores body) | OK |
| InterviewRoomView, InterviewsView | DELETE `/interviews/{id}` | none | 204 | OK |
| CodeEditorPanel | GET `/interviews/{id}/problem` | none | `ProblemOut`; `review_job_id` only set while submission.status == review | OK matches `types/coding.ts` |
| CodeEditorPanel | POST `/interviews/{id}/submissions` | `{language, code}` | language 1..30, code 1..8000; 202 `{job_id, submission_id}`; failure frees the single submit (`mark_failed`) | OK |
| ReportsView, ReportDetailView, useReportGeneration | GET `/reports`, GET/DELETE `/reports/{id}`, POST `/interviews/{id}/report` | none | `ReportSummaryOut`, `ReportOut{report: dict}`, `{ready, job_id}`; the report dict built in `reports/service.py:178-200` has exactly the keys of `ReportData` (version, interview{id,type,started_at,minutes_used}, overall_score, band, verdict, dimensions[], strengths[], improvements[], phase_notes[], next_steps[], coding[], stats, disclaimer); coding facts match `ReportCoding` | OK |
| AtsScoreView | POST `/ats/score` | `{resume_id, jd_text, provider}` | `ScoreResponse` incl. `coverage[]`, `history_id` | OK; limiter 6/min |
| AtsHistoryPanel | GET `/ats/history?resume_id&limit=10`, GET/DELETE `/ats/history/{id}` | none | `AtsHistoryItemOut[]`, `AtsHistoryDetailOut{result}`; stored result has every key `ScoreBreakdown` reads | OK |
| ResumesView | POST `/rag/resumes/{id}/process` | none | `ProcessResumeResponse` | OK |
| TeamManager | GET `/team/users`, PATCH `/team/users/{id}/role` `{role}`, PUT `/team/users/{id}/permissions` `{permissions}` | | `TeamUserOut`, `RoleOut`, `PermissionsOut` (permissions max 20) | OK |
| QuestionBankView | GET `/interviews/question-bank`, POST, PATCH, DELETE `/interviews/question-bank/{id}` | create: type, question, solution_code?, solution_language?, tags, topic?, difficulty?; edit: everything, null clears topic/difficulty | `QuestionIn`/`QuestionUpdateIn` (question 1..4000, solution 8000, language 30, topic 60, difficulty 1..5); explicit null clears topic/difficulty; empty `solution_code` rejected for coding types (UI pre-checks) | OK. Permission enforced server-side (`_require_permission`) |
| NotificationsBell | Supabase `notifications` select (id, message, is_read, created_at) and update `is_read` | n/a | RLS select/update own (`0011`) | OK |
| guards.ts | Supabase `profiles`, `provider_keys` (id,user_id,provider,slot,is_valid), `roles`, `admin_permissions` | n/a | column grant on `provider_keys` includes those columns (`0019`); `roles_select_own`, `admin_permissions_select` | OK |
| AccountSetupForm / DemoSignUpView | Supabase `profiles.insert({id, full_name})` | n/a | `profiles_insert_own`; role trigger | OK |
| api/resumes route | Supabase `resumes` select/insert/update/delete; `insert` limited to (id, user_id, file_key), `update` to display_name (`0028`); trigger error text contains `resume_limit` (matched by the handler) | n/a | OK |
| api/resumes POST | fetch `${API}/rag/resumes/{id}/process` with the user's bearer token | none | reads `body.detail` of the error envelope (present as a string) | OK |
| fastapi.ts | error parsing `{error:{code,message,request_id}, detail}` | | `core/errors.py` envelope; validation errors via `detail[].msg` also handled | OK |

Error-code strings compared by the UI: `interview_not_cancellable`, `interview_ended` (both emitted by the backend), `resume_limit` (emitted by the Next route itself). **No contract mismatches found.**

## 4. Findings

Ranked. Every item below was confirmed by reading the cited code (backend side read where relevant). Severity reflects impact for a BYOK app with a single owner today.

### CRITICAL
None.

### HIGH
None confirmed. (The closest are M-3 to M-6, which break voice mode behaviour but never lose data.)

### MEDIUM

**M-1 No HTTP security headers.** `next.config.ts:3-5` is empty and the live response of `/sign-in` carries only `x-powered-by`; no CSP, `X-Frame-Options`/`frame-ancestors`, `Referrer-Policy`, `X-Content-Type-Options`, `Permissions-Policy` (microphone is used). Scenario: the key-entry form and the destructive buttons can be framed by any site (Supabase cookies are SameSite=Lax which limits but does not remove the risk), and any future XSS has no CSP backstop. Fix: add `headers()` in `next.config.ts` with `X-Frame-Options: DENY` (or `frame-ancestors 'none'`), `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy: microphone=(self), camera=()`, and a CSP that allows the Supabase/API origins and jsdelivr for Monaco (or self-host Monaco, see M-14).

**M-2 Temporary demo sign-up route ships and is linked.** `app/(auth)/sign-up/page.tsx:1-3`, `DemoSignUpView.tsx:1-10` ("DO NOT SHIP"), `SignInView.tsx:72-79` ("Create a demo account (dev only)"). It is in the production build as a static page. Scenario: anyone can create an email/password account against the production Supabase project (if email sign-up is enabled there), contradicting the Google-only model in IMPLEMENTATION.md section 7; migration `0010` also makes the first profile ever created the Owner, so on an empty database the first visitor to `/sign-up` becomes Owner. Fix: delete the route and the link before public launch, or gate both on `process.env.NODE_ENV !== "production"`; disable email sign-ups in Supabase Auth settings.

**M-3 Turning voice on does not read the pending interviewer question.** `InterviewRoomView.tsx:105-111` calls `voice.speak(last)` in the same tick as `changeVoiceSettings({enabled: true})`; `useVoice.ts:82` returns early because `live.current.active` is only refreshed in an effect after the next render, so the call is a no-op. The bar text says "Answer out loud and hear the interviewer". Scenario: candidate clicks "Turn on voice" mid-interview; the mic starts but the open question is never spoken, and `spoke.current` never becomes true so no nudge either. Fix: skip the `active` check for an explicit user-initiated call (`speakInternal(text, {force: true})`), or speak from an effect when `active` flips to true.

**M-4 The interviewer's closing message is cut off when time runs out.** `InterviewRoomView.tsx:256-258` speaks the reply, then awaits `autoComplete()`; the status flips to `completed`, `useVoice` `active` goes false and `useVoice.ts:197-211` calls `cancelSpeech()` within about a second. Scenario: final-phase answer, the wrap-up ("thanks, that's all") starts and is silenced mid-sentence. Fix: do not cancel speech on `active -> false` caused by completion (only on the user's own "Turn off voice"/unmount), or delay `autoComplete` until `voice.speaking` is false.

**M-5 `speak()` race flips `speaking` to false while the new utterance is playing.** `useVoice.ts:80-92`: a second `speak` cancels the first (`synthesizer.ts:34-41`), the first promise resolves later and runs `speakingRef.current = false; setSpeaking(false)` after the second already set them true. Scenario: the 20 s nudge ("Take your time") is speaking while the candidate sends a typed answer; the reply's `speak()` supersedes it, then `speaking` drops to false mid-reply, `shouldListen` (line 66-68) becomes true and the microphone transcribes the interviewer's own voice as the candidate's next answer. Fix: capture a token in `speakInternal` and only reset state if it is still the latest speak.

**M-6 Microphone error latches until page reload.** `useVoice.ts:66-68` stops listening permanently once `error` is `not-allowed` or `audio-capture`; the error is cleared only in `onStart` (never reached) and `clearError` (`:251`) is exported but never called (grep: zero callers; VoiceBar does not offer it). Scenario: candidate blocks the mic, reads "Allow it in your browser's address bar", allows it, toggles voice off/on: still "Microphone access is blocked". Fix: call `clearError()` from `VoiceBar`'s enable/disable buttons (or on `settings.enabled` change) and add a "Try again" button next to the error.

**M-7 Guards ignore Supabase query errors, so a transient failure routes an existing user to account setup / onboarding.** `lib/auth/guards.ts:22-43`: `profile`/`geminiKey` are read without checking `error`; a failed query is indistinguishable from "no row". Scenario: a 500 from Supabase during a hard load sends an existing user to `/account-setup`, whose form lets them set a new password (it calls `auth.updateUser`) before the profile insert fails on a duplicate. Fix: destructure `error` and throw (so the error boundary shows a retry) instead of redirecting; add `error.tsx`.

**M-8 Resume upload route buffers the whole body before checking size, and its server-side processing fetch has no timeout.** `app/api/resumes/route.ts:53` (`request.formData()`) runs before the 500 KB check at `:71`; `:124` `fetch(.../process)` has no `AbortSignal`. Scenario: an authenticated user posts a 1 GB body and the handler buffers it; separately, a cold API (free tier wakes in about a minute, embedding can take longer) holds the upload request and spinner for as long as the platform allows. Fix: reject early on `Content-Length > 600 KB` (and stream-limit), add `AbortSignal.timeout(120_000)` to the processing fetch and return `processingError` on timeout (the UI already offers "Retry processing").

**M-10 JavaScript smooth scrolling ignores `prefers-reduced-motion`.** `ChatWindow.tsx:32`, `InterviewRoomView.tsx:134`, `AtsScoreView.tsx:88,101,112` call `scrollIntoView({behavior:"smooth"})`; an explicit `behavior` is not overridden by the CSS rule in `globals.css:398`. Every CSS and framer-motion animation is covered (verified: global `animation/transition-duration` override, `MotionConfig reducedMotion="user"`, `CountUp`, `LoadingScene`, view transitions), so this is the one hole. Fix: a tiny helper `scrollOpts()` returning `behavior: matchMedia(...).matches ? "auto" : "smooth"`.

**M-11 "Save as PDF" in dark theme prints dark panels.** `globals.css:412-432` only forces body colours; the dark tokens still apply to `bg-card` (dark `#111426` with light text) and `print-color-adjust: exact` makes them print. Scenario: report printed from dark mode is a mostly dark page. Fix: inside `@media print` re-declare the light token values on `:root` (or remove the `dark` class on `beforeprint`).

**M-12 Failing "Show older interviews" blanks the whole list.** `InterviewsView.tsx:59-61` writes the error into the page-level `error` state, which makes the render at `:109` replace the already loaded list with the error block. ChatListView toasts instead. Fix: use `toast` like `ChatListView.loadMore`.

**M-13 (needs verification, Supabase behaviour) Account-setup retry after a partial success can dead-end.** `AccountSetupForm.tsx:55-84`: `updateUser({password})` succeeds, the profile insert then fails (network/RLS); the retry sends the same password again, and Supabase rejects an unchanged password (`same_password`), so the user must pick a different one. Fix: treat that specific error as success and continue, or insert the profile first.

**M-14 Monaco loads from a third-party CDN at runtime.** `CodeEditorPanel.tsx:16` uses `@monaco-editor/react` with its default loader (jsdelivr). No SRI, no offline fallback (the editor shows the skeleton forever, no error state), blocked by any future CSP, and `privacy/page.tsx` does not mention this extra third party (it sees the user's IP). Fix: configure `loader.config({ paths: { vs: "/monaco/vs" } })` with self-hosted files, or at least add a timeout and a "Could not load the editor, type in the box below" textarea fallback, and add one line to the privacy page.

### LOW

- **L-8** `OnboardingFlow.tsx:25-27`: a failed `/keys` load shows an error with no retry (ApiKeysView has one).
- **L-9** `fastapi.ts:158-186` `streamPost`: no timeout, no abort signal, no wake retry. Leaving the page mid-stream leaves the reader running (`ChatWindow.tsx:60`); a send to a sleeping server fails immediately with "Couldn't reach the server" and no banner (the draft is restored, so no data loss).
- **L-14** Privacy page omits the Monaco CDN (see M-14) and says localStorage keeps "an unsent code draft" while submitted code drafts also remain (L-17).
- **L-15** No `error.tsx`, `global-error.tsx`, `not-found.tsx`, `loading.tsx`: default unbranded Next screens for any server error or unknown URL; page transitions show nothing until each client view's own skeleton.
- **L-16** `InterviewRoomView.tsx:313-324` and the whole room have no `<h1>`; only the phase badge. Screen-reader users land in `main` with no page heading.
- **L-17** `CodeEditorPanel.tsx:55-74`: drafts are written to `localStorage` per problem and never removed (no `removeItem` anywhere), including after a successful submit. Code stays on a shared machine indefinitely.
- **L-18** Chat thread loads only the latest 200 messages (backend `DEFAULT_MESSAGE_PAGE=200`) with no "older messages" control; a longer thread silently shows a truncated history. (`ChatThreadView.tsx:53`.)
- **L-19** Every dashboard page has the same `<title>` "CyntraAI" (only `/privacy` sets one). WCAG 2.4.2.
- **L-20** Interview in `setting_up` shows a static message (`InterviewRoomView.tsx:438`) with a manual Refresh; nothing polls, so a user who navigated away from the setup screen and comes back must click Refresh.
- **L-21** `ReportDetailView.tsx:244-247` uses `key={line}` and `:275-277` `key={s}`: duplicate model-generated lines produce duplicate React keys. Use the index.
- **L-22** Global `serverStatus.setWaking` boolean (`fastapi.ts:136,149`): when two GETs retry concurrently the first to finish hides the banner while the other still waits. Use a counter. Also worst-case a GET retries 7 x 30 s + 55 s of back-off (about 4.5 min) before showing an error.
- **L-23** `NotificationsBell.tsx:42-49` polls every 60 s even when the tab is hidden; skip when `document.hidden`.
- **L-24** Dead code: `components/ui/StubPage.tsx` (no importer), `HomeIcon`/`InboxIcon` (`icons.tsx`), `ScoreRequest` (`types/ats.ts`), exports only used internally (`TypingDots`, `MAX_RESUME_BYTES`, `RESUME_EXTENSIONS`, `CONFIRM_MS`, `NUDGE_AFTER_MS`, `pickVoice`, types), the 5 `public/*.svg` templates, unused CSS tokens `--ease-in-out` and `shadow-xl`, unused deps `zod`, `zustand`, `@react-three/drei`, boilerplate `README.md`.
- **L-25** `npm audit` (see section 1): `npm audit fix` clears the two low prod findings (dompurify via monaco-editor).
- **L-26** Timer: `minutesRemaining` comes from the client clock (`ends_at - Date.now()`, `InterviewRoomView.tsx:124,142`), so a skewed device clock shows a wrong countdown; when time expires with an idle candidate the room stays open until the next send (server then answers `interview_ended`, handled at `:266`).
- **L-27** "Get my report" in the room (`InterviewRoomView.tsx:463`) goes to the `/reports` list, where the user must click a second "Get my report". Either rename or deep-link to a start-and-wait flow.
- **L-28** `ReportsView.tsx:38-43`: "Completed interviews without a report" is computed from the first 50 interviews only (`GET /interviews` default page); older completed interviews cannot get a report from this page. Same 50 cap for `/reports`.
- **L-29** `GET /api/resumes` (`route.ts:154`) returns the full `parsed_text` of every resume to list screens (3 x tens of KB); the lists only need a boolean. Select `parsed_text IS NOT NULL` or a length via a view.
- **L-30** `ProviderKeySection.tsx:28-33`: `upsertKey` closes over the render-time `keys`; saving the primary and backup key of one provider concurrently can overwrite one update with the other. Use a functional updater in the parent.
- **L-31** `useVoice.ts:98-111`: nudges ("Take your time", "Let me repeat that ...") ignore typing and the code editor; during a long coding round with voice on, the interviewer interrupts the candidate twice per question.
- **L-32** `CodeEditorPanel.tsx:157-161`: the draft is saved only when the code changes, so a language change alone is lost on reload.
- **L-33** `InterviewSetupView.tsx:98,147-150`: cancelling while the POST is in flight and re-submitting before it returns resets `cancelled.current = false` (needs verification; narrow race).
- **L-34** Poll give-up times vs server worst cases (needs verification): setup 4 min, review 3 min, report 5 min. Backend per-call deadline is 2 x timeout + 10 s (`judge` 45 s -> 100 s; `report` 60 s -> 130 s; default 30 s -> 70 s); a review with the schema-repair retry, or a setup with several calls, can exceed the review/setup limits. The UI then says "taking longer than expected" while the job later succeeds; setup leaves a `setting_up` interview.
- **L-35** No `apps/web/.env.example`; required vars (`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_API_URL` without trailing slash, `STORAGE_*`) are only listed in `docs/PHASE10_PLAN.md` and the CI file.
- **L-36** `/sign-in` and `/sign-up` do not redirect an already signed-in user.
- **L-37** Internal links use `<a href>` (full reload) in `AuthShell.tsx:82`, `SignInView.tsx:74`, `DemoSignUpView.tsx:114,164`; use `Link`.
- **L-38** `NotificationsBell`: opening the panel does not move focus into it, and Tab out of the panel does not close it (Escape and outside-click do).
- **L-39** (needs verification) `ChatWindow.tsx:92` `role="log" aria-live="polite"` while a reply streams in one node: screen readers may announce every chunk update.
- **P-1 Performance: duplicated auth waterfall.** `requireUser` (`guards.ts:12-63`) does `auth.getUser()` (network) plus 3-4 sequential queries, runs in the layout and again in `DashboardHome`, `TeamView`, question-bank page, and `proxy.ts` calls `auth.getUser()` per request as well. Wrap `requireUser` in React `cache()` and run the independent queries with `Promise.all`; saves several round trips per hard load.

### Needs verification (could not be confirmed statically)
1. M-13 (Supabase `same_password` behaviour).
2. L-33 (cancel/resubmit race), L-34 (worst-case job durations), L-39 (screen-reader chatter).
3. Whether Supabase email sign-up is actually enabled on the production project (decides how serious M-2 is).
4. Behaviour in Safari/Firefox of voice (SpeechRecognition unsupported there; the UI degrades to a note, verified in code only).

## 5. Per-screen verdict

| Screen | Verdict (static) | Issues |
|---|---|---|
| Sign-in (Google, email) | works | L-36, L-37 |
| Sign-up (demo) | works but must not ship | M-2 |
| Account setup | works | M-13 |
| Onboarding | works | L-8 |
| Dashboard home | works | P-1 |
| Chat list (new, rename, delete, older) | works | none |
| Chat thread (stream, copy, rename) | works | L-9, L-18, L-39 |
| Resumes (upload, rename, retry, delete, limit 3) | works | M-8, L-29 |
| ATS score + history | works | M-10 |
| Interviews list | works | M-12 |
| Interview setup (+cancel) | works | L-33, L-34 |
| Interview room, typed | works | L-16, L-20, L-26 |
| Interview room, voice | partly | M-3, M-4, M-5, M-6, L-31 |
| Coding round (editor, confirm, review polling) | works | M-14, L-17, L-32, L-34 |
| Reports list / generate | works | L-27, L-28 |
| Report detail (print, download, delete) | works | M-11, L-21 |
| Settings: API keys + usage | works | L-30 |
| Team | works | none |
| Question bank | works | none |
| Notifications bell | works | L-23, L-38 |
| Theme toggle, sign out | works | none |
| Privacy | works | L-14 |

Items explicitly verified OK: no `window.confirm/alert/prompt`; no `dangerouslySetInnerHTML`/`innerHTML`; model-generated text is rendered as text everywhere (chat, ATS, report, coding issues); external links use `rel="noreferrer"`; only the anon key and API URL are `NEXT_PUBLIC_`; `lib/storage.ts` is `server-only` and imported only by route handlers; route handlers authenticate, scope by `user_id`, validate extension/size/signature/name length, and the DB enforces limit and column grants; localStorage holds only voice settings and code drafts; no hydration mismatches found (client-only dates, `useSyncExternalStore` for mount/media); contrast table below; no unmount leaks found in polling loops (they check `mounted`) or intervals (all cleaned up).

Contrast (WCAG ratios computed from `globals.css`, light / dark): foreground on background 16.96 / 16.44; muted-foreground on card 6.50 / 7.23 and on secondary 5.71 / 6.50; primary on background 7.45 / 7.15; primary-foreground on primary 7.90 / 7.15; accent-foreground on accent 8.63 / 8.15; destructive on soft 5.59 / 7.31; success on soft 6.29 / 8.98; warning on soft 5.11 / 9.14; info on soft 5.75 / 7.22; input border on card 3.60 / 3.15 (>= 3:1 for controls); placeholder (muted at 85%) 4.57 light. Fill tokens for graphics: 3.30, 3.19, 4.83 on white. All text pairs pass AA.

## 6. Test gaps

Existing: 24 files, 158 tests, all passing. Strong on destructive flows, rename, route handlers (18), confirm dialog, toast, notifications. Weaknesses and gaps:

1. **`lib/api-client/fastapi.ts` has zero tests** (retry/back-off, 401 redirect, envelope parsing, timeouts, waking banner). Every other test replaces it with a mock.
2. **`useVoice`, `VoiceBar`, `synthesizer`** untested; both room test files mock `useVoice` away entirely, so M-3 to M-6 cannot be caught. Only the pure buffer/text/settings helpers are tested (and the ATS feedback parser lives in `voice.test.ts` by mistake).
3. **CodeEditorPanel**: no test for review polling failure/timeout, resuming a review after reload (`review_job_id`), draft restore, language "Other", too-long code.
4. **`ScoreBreakdown`** is mocked in both ATS test files, so its rendering (verdict bands, coverage details) is untested.
5. **Report generation** (`useReportGeneration`, "Get my report" button) untested; `ReportsView` tests cover delete and load error only.
6. **InterviewSetupView**: only cancel and the resume-name dropdown are tested; no happy-path polling, failed job, or timeout test.
7. **Load-more paths** (`ChatListView`, `InterviewsView`) untested (M-12 would have been caught).
8. **Auth layer untested**: `guards.ts`, `proxy.ts`, `auth/callback/route.ts`, `SignInView`, `AccountSetupForm`, `DemoSignUpView`, `OnboardingFlow`, `DashboardShell`/`NavLinks` (including the owner/permission nav items).
9. **No tests**: `ApiKeysView`, `UsageToday`, `ThemeToggle`, `SignOutButton`, `ServerWakingBanner`, `PhaseTimer`, `LoadingScene`, `DashboardHome`, privacy page.
10. `POST /api/resumes` success path including the processing fetch and its failure is not covered (the route tests mock storage and Supabase; they do test limit, signature, trigger mapping).
11. No accessibility tooling (jest-axe/Playwright axe) and no end-to-end test.
12. Tests that mock the thing under test: room tests mock Monaco panel and voice (acceptable for the room, but nothing covers the integration); `ChatRename.test` mocks `ChatWindow`.

## 7. Upgrades worth doing (prioritised)

1. Before launch: remove or gate the demo sign-up (M-2) and add security headers (M-1).
2. Fix the four voice bugs (M-3 to M-6) and add a `useVoice` hook test with a fake recognizer/synthesizer; they are small, local changes.
3. Add `error.tsx` / `not-found.tsx` / `loading.tsx` and make the guards throw on query errors (M-7, L-15).
4. Test the API client (retry, 401, envelope) and the guards; these are the least-tested, most load-bearing files.
5. Self-host Monaco or add a timeout and fallback textarea (M-14).
6. Wrap `requireUser` in `cache()` and parallelise its queries (P-1); consider a `/dashboard` summary to avoid the five-call hard-load waterfall.
7. Upload route: early size rejection and a processing timeout (M-8).
8. Reduced-motion helper for JS scrolling (M-10); light tokens in `@media print` (M-11).
9. Per-page titles via `metadata` exports (L-19), a heading in the room (L-16), and focus handling for the notifications panel (L-38).
10. Cleanup: delete `StubPage`, unused icons/type/svgs/deps, replace README, add `apps/web/.env.example` (L-24, L-35); run `npm audit fix` (L-25).
11. Nice UX: auto-poll `setting_up` rooms (L-20), older-messages control in chat (L-18), remove drafts after submit (L-17), `LazyMotion` to trim the shared framer-motion weight.
