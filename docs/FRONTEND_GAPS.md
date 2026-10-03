# Frontend gaps: audit, fixes and open backend work

Scope: `apps/web`. Second pass after the UI refresh (`docs/UI_REFRESH.md`). Status key: **Fixed** (code changed and covered by a test where noted), **Backend** (needed a backend/database change, see section 3, all now built), **Left** (deliberately not done, see section 4).

## 1. The reported bug: "Delete does nothing on the Resumes page"

Traced path: button click -> `window.confirm` -> `fetch DELETE /api/resumes/:id` -> route handler -> Supabase `resumes` delete under RLS -> storage delete -> UI state.

| Step | Finding |
|---|---|
| `window.confirm(...)` in `ResumesView.handleDelete` | **Root cause.** `if (!window.confirm(...)) return;` is the first line. Embedded webviews, "prevent this page from creating dialogs" and some browsers make `confirm` return `false` immediately and without any UI. The handler then returns before any request is made: no request, no error, no message. The same pattern existed in `QuestionBankView`, `ProviderKeyForm` and `ReportDetailView`. |
| Route handler `app/api/resumes/[id]/route.ts` | Correct for the happy path (ownership check, delete, 204). Two weaknesses fixed: it answered 204 even if the delete matched zero rows, and it awaited the S3 delete with no time limit, so a dead storage endpoint could hold the response for a long time. |
| RLS (`0006`, `0009`) | `resumes_owner_only` is `for all using (user_id = auth.uid()) with check (...)`: delete is allowed for the owner. Not a cause. |
| FKs (`0013`, `0019`) | `resume_chunks.resume_id` is `on delete cascade`; `interviews.resume_id` is `on delete set null` since `0019`. If migration `0019` had not been applied to a database, the delete would fail with a foreign key error; that error is now shown in the dialog (and was shown in the old inline alert), so it would not be silent. Owner should confirm `0019` is applied. |
| Optimistic update / rollback | Rollback existed and the error was shown at the top of the page, so a failing request was visible. It could not produce "nothing happens". Replaced by a non-optimistic flow anyway: the row leaves only after the server says yes. |
| `AnimatePresence` / `layout` | Does not intercept clicks; exit animation only runs after the item is removed from state. Not a cause. |
| Stale closure | `handleDelete(id)` reads no stale state except `resumes` for rollback. Not a cause. |

Fix: every destructive action now goes through the in-app `ConfirmDialog` (no `window.confirm/alert/prompt` anywhere in `app/`, `components/`, `lib/`; verified by search). Failures appear inside the dialog and the row stays. The regression test `ResumesView.test.tsx` stubs `window.confirm` to return `false` and still expects the DELETE call, so it fails on the old code.

## 2. Gap table

Severity: H = data loss, silent failure or blocked flow; M = misleading or inaccessible; L = polish.

| ID | Screen | Problem | Root cause | Fix | Status |
|---|---|---|---|---|---|
| G01 | Resumes | Delete does nothing, no message | `window.confirm` returns false silently | `ConfirmDialog` + `useConfirm`; non-optimistic delete; error inside the dialog (H) | Fixed, tested |
| G02 | Question bank, API keys, report detail | Same `window.confirm` dependence | Same | All routed through `useConfirm` (H) | Fixed, tested |
| G03 | `DELETE /api/resumes/:id` | 204 even when no row was deleted; storage delete could hang the response | No row count check, no timeout | `.delete().select("id")`, 409 when empty, 8 s race on storage delete (M) | Fixed, tested |
| G04 | Question bank | Failed delete rolled back with no message | `catch { setQuestions(previous) }` | Error shown in the dialog, success toast (H) | Fixed, tested |
| G05 | Interview room | "End interview" ended the interview with one click, no confirmation, no pending state | Direct `handleComplete` | Confirm dialog with explanation, loading button, failure shown in dialog, success toast (H) | Fixed, tested |
| G06 | Report detail | A failed delete replaced the whole report with an error page | Delete error reused the page-level load error state | Dialog error; report stays on screen (H) | Fixed, tested |
| G07 | ATS score, Interview setup | `fetch("/api/resumes").then(r => r.json())` fed a `{error}` object to `.filter` when the call failed: generic error, or a misleading "No processed resume yet" | No `res.ok` check, no array check | `fetchResumes()` in `lib/resumes.ts` throws readable errors; load error state with Try again, separate from the real empty state (H) | Fixed, tested |
| G08 | Chat list | A failed "New chat" replaced the conversation list with an error | One `error` state for load and action | Action errors are toasts, load errors stay a separate state (M) | Fixed, tested |
| G09 | Notifications bell | Mark-all-read never rolled back or reported failure; no per-notice mark read; Escape did not return focus; no panel id | Fire and forget update | Rollback + error toast, per-notice "Mark read", refresh failure notice with Retry, focus returns to the bell, `aria-controls` (M) | Fixed, tested |
| G10 | Settings usage card | A failed usage request showed "No requests yet today" | `.catch(() => setRows([]))` | Honest error with Try again (M) | Fixed |
| G11 | Interviews list, header actions | `<Link><Button/></Link>`: interactive element nested in another | Wrapper pattern | `LinkButton` (a real link styled as a button) and `ListRow` (stretched title link, actions above it) (M) | Fixed |
| G12 | Resumes | No limit on the number of resumes | Not implemented | Limit of 3 enforced in `POST /api/resumes` (409 `resume_limit`), "N of 3 used", upload disabled at 3 with the reason (M) | Fixed, tested (server-side enforcement only in the Next handler, see B07) |
| G13 | ATS, Interview setup | The API requires a job description of 10 to 20000 characters; the UI only checked non-empty, so a short text produced an unexplained 422 | Missing client validation | Inline hint + counter, button enabled only when valid (M) | Fixed, tested |
| G14 | API key form | Obviously truncated key sent to the API; no success feedback beyond inline text | No validation, no toast | Min length check, toast on save, field `maxLength` (L) | Fixed, tested |
| G15 | Chat, Interview room | Single-line composer; Enter-only; focus lost after send; no length limit in chat | `<input>` | Auto-growing `<textarea>`: Enter sends, Shift+Enter new line, IME safe, `maxLength` (chat 8000, answer 4000 per API), focus returns after send (M) | Fixed, tested |
| G16 | All list/detail pages | A failed load had no way to retry | Error alert only | "Try again" on chat list/thread, interviews, reports, report detail, keys, usage, resumes, question bank, ATS/setup, interview room (M) | Fixed |
| G17 | Chat list | No way to delete a conversation | No UI | Delete via the user's own Supabase session (RLS `conversations_owner_only`; messages cascade), confirm dialog, toast (M) | Fixed, tested |
| G18 | Reports list | No way to delete a report from the list | No UI | Delete through the existing `DELETE /reports/{id}` with the dialog (L) | Fixed, tested |
| G19 | Interview code panel | "Yes, submit" gave no feedback until polling began; focus vanished when the confirm row replaced the Submit button | No pending state | Loading state, `autoFocus` on "Keep editing", `role="group"` label (M) | Fixed, tested |
| G20 | Account setup, demo sign-up | Inputs without associated labels, no autocomplete hints, no password rule shown | Placeholder-only / unassociated labels | `htmlFor`/`id`, aria-labels, `autoComplete`, rule text (M) | Fixed |
| G21 | Sign out | No pending or error state | Fire and forget | Spinner, disabled while working, error toast (L) | Fixed |
| G22 | Chat | No way to copy a reply | Not implemented | Copy button under assistant messages with toast (L) | Fixed, tested |
| G23 | API keys | Deleting the Gemini primary key gave no warning although it sends the user back to onboarding | Generic confirmation | Specific warning in the dialog (M) | Fixed, tested |
| G24 | Report download | Anchor was not attached to the DOM before `click()` (Firefox) | Detached anchor | Attached, removed, delayed `revokeObjectURL`, toast (L) | Fixed |
| G25 | Interview room | An interview stuck in `setting_up` was a dead end ("This interview is setting_up") | No state handling | Plain explanation + Refresh button; `aborted` and finished texts (M) | Fixed |
| G26 | Question bank | Editing a question did not bring the form into view; no keyboard save; unlabeled inputs (question, tags) | No focus handling | Scroll + focus on edit, Ctrl+Enter, aria-labels, `maxLength` 4000, note that topic/difficulty cannot be cleared (M) | Fixed (clearing: see B04, done in Round 3) |
| G27 | Everywhere | Several rows each had a button just called "Delete" | Visible-text-only names | Specific `aria-label`s ("Delete file-1.pdf", "Delete groq primary key") (M) | Fixed |
| G28 | Chat list, Interviews list | Only the newest 50 were ever shown, silently | Server page size 50, no paging UI | "Show older chats/interviews" loads the next page (M) | Fixed |
| G29 | Chat thread | A chat with no usable key just had a disabled composer | No guidance | Message with a link to API Keys (L) | Fixed, tested |
| G30 | Team (owner) | Page is a stub saying "Coming in a later build phase" | No backend | Wording made honest; see B03 | Fixed in Round 3 (see B03) |
| G31 | Resumes | Upload errors only appeared after a round trip (wrong type, empty, > 500 KB) | Server-only validation | Same rules checked in the browser first (`validateResumeFile`), server still authoritative (L) | Fixed, tested |
| G32 | Layout | Locking page scroll for a dialog made the page jump sideways by the scrollbar width | No stable gutter | `scrollbar-gutter: stable` on `html` (L) | Fixed |

Audited and found sound (no change needed): sign-in (Google, email/password, demo link), onboarding steps and Gemini gate, theme toggle, mobile nav, skip link, voice features (not touched), job polling in interview setup, report generation and the print layout, code draft persistence, server-waking banner, interview turn error rollback.

## 3. Backend work (all B01-B08 are now built and wired in the UI, Round 3)

| ID | Feature | Status and what the UI does |
|---|---|---|
| B01 | Rename a resume | **Done.** `PATCH /api/resumes/[id]` (Next route handler, owner-scoped update of `display_name` only, trimmed, empty becomes null, 1-80 characters, 400/401/404). `GET /api/resumes` selects `display_name`; `resumeName()` returns `display_name ?? file name` and is used by the Resumes page, the ATS and interview-setup dropdowns. Inline rename (pencil, Enter saves, Escape cancels, validation message, toast, inline error) on the Resumes page. |
| B02 | ATS score history | **Done.** "Previous checks" panel under the ATS form for the selected resume: list (mini ring, job title or "Untitled role", relative date, excerpt), open a saved result in the same breakdown with a "Saved result from ..." banner and "Run a new check", delete with confirm and toast, skeleton, empty state, error with retry, quiet refetch after every new score (`history_id` marks the new row as "Showing"). Note shown: the last 10 checks per resume are kept. |
| B03 | Team management (Owner) | **Done.** `app/(dashboard)/settings/team`: server component keeps `requireRole("owner")`, client `TeamManager` lists users (avatar initials, role badge), "Make admin" / "Make user" (confirm when demoting), permission checkboxes from one constant (`lib/team.ts`), optimistic updates with rollback and error toasts, search above 8 users, skeleton, empty and error states. Owner row and your own row are read-only; plain users show disabled permissions with a hint; demoting clears permissions locally. The "Not available yet" stub is gone. |
| B04 | Clear topic or difficulty of a question | **Done.** On edit, an emptied topic or a blank difficulty is sent as an explicit `null`; on create empty fields are still omitted. The "cannot be cleared" note is replaced by a hint. Tested. |
| B05 | Cancel an interview setup | **Done.** Setup page shows a "Cancel" button while the job runs: stops polling, `POST /interviews/{id}/abort`, toast, back to the form (handles a cancel pressed before the start response arrived, and the 409 `interview_not_cancellable` case by opening the interview). The room offers "Cancel setup" for `setting_up` instead of the dead end. |
| B06 | Delete an interview | **Done.** Delete on every interviews list row and in the room's finished state (completed or aborted), with a confirm dialog that names the transcript, code and report, a toast, and removal from the list state. Interviews with `resume_id: null` still link to the room. |
| B07 | Enforce the 3-resume limit in the database | **Done (UI side).** The trigger error (message starting `resume_limit`, code P0001) is mapped in `POST /api/resumes` to the same 409 `{error, code: "resume_limit"}` as the pre-check (the stored object is cleaned up). The pre-check stays. |
| B08 | Rename a conversation | **Done.** `PATCH /chat/conversations/{id}` from an inline rename on chat list rows and in a new thread header (title 1-120, trimmed, validation, toast). The header reads the title through the user's own Supabase session because the API has no single-conversation GET. |

## 4. Deliberately left alone

- Backend, migrations, `.env` files and anything under `apps/api` (constraint).
- Voice features, Monaco loading, three.js scene, report print layout (kept working).
- The temporary demo sign-up route and its link (marked temporary in the code; owner decides when to remove).
- Undo for deletes: a true undo would mean deferring the real DELETE (lost if the tab closes) or restoring rows the API cannot recreate (resume files, report text). The confirmation dialog plus a "deleted" toast was chosen instead.
