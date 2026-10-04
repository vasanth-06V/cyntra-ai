# Phase 8 — Voice (plan, for approval)

Status: **APPROVED 2026-10-03. BUILT and committed (frontend only, no migration, no backend change; `apps/api/app/interviews/voice/` is an empty leftover package). Awaiting the owner's hands-on test in Chrome/Edge: nothing in this document has been verified with a real microphone. The final frontend audit (2026-10-04) found four bugs in the voice layer (turning voice on mid-interview does not read the pending question; the closing message can be cut off when time runs out; a `speak()` race can let the microphone hear the interviewer; a microphone error latches until reload; see `docs/audit/FRONTEND_AUDIT.md` M-3 to M-6) and that nudges ignore typing (L-31). Browser behaviour (Chrome/Edge good, Safari partial, Firefox none) comes from documentation and is unverified.**
Constraints: free tier only; the interview conversation is the product; the text pipeline (turns, jobs, atomic writes, coding round) already works and must not be rewritten.

## 1. The decision: voice as an I/O layer, in the browser

Instead of a new realtime backend (Gemini Live over WebSockets), voice becomes a thin layer around the existing turn endpoint:

```
candidate speaks ─► browser speech recognition ─► text ─► POST /interviews/{id}/turns (unchanged)
                                                              │ interviewer's reply text
candidate hears  ◄─ browser speech synthesis ◄────────────────┘
```

| | Browser voice (proposed) | Gemini Live (original idea) |
|---|---|---|
| Cost | **free, no quota** | free-tier limits unknown (unmeasured) |
| Backend changes | **none** (reuses `/turns`) | WebSocket server, ticket auth, `google-genai` migration, session resumption for the 15-min cap |
| Session length | unlimited | 15 min per session, needs resumption for a 60-min interview |
| Voice quality | system voices (decent on Chrome/Edge, varies) | natural, expressive |
| Latency | LLM turn time (~1–3 s) + instant speech | lower, streamed audio |
| Privacy | Chrome's recognizer sends audio to Google's service (stated in the UI) | audio goes to Google (the key owner's quota) |
| Browsers | Chrome/Edge (desktop, Android) good; Safari partial; **Firefox no speech recognition** → typing fallback | any browser |
| Risk | echo (the mic hearing the speakers) → headphones advised | quota and concurrency unknown |

Everything the product already guarantees (transcript in the database, atomic turns, 60-minute timer, injection defenses, token budgets) stays exactly as it is, because the text is the same text.

**Upgrade path (not now):** the voice layer sits behind a small `VoiceIO` interface (`listen()`, `speak()`, `stop()`), so a premium implementation (Gemini TTS or Live) can be added later after an owner-run prototype measures the free-tier limits. If measurements show Live is usable on the free tier, it becomes an optional second implementation.

## 2. What the candidate experiences

1. **Voice mode switch** in the interview room (on by default only where supported; typing always available). First use asks for microphone permission with a one-line explanation (including the Chrome recognizer note).
2. **The interviewer speaks** each reply aloud (while the text appears in the transcript as now). A "Stop speaking" button and a speaking indicator.
3. **The candidate answers by voice:** live captions show what is being heard; after a configurable pause of silence (default 2.5 s, adjustable 1.5–4 s) the answer is sent automatically with a short visible "Sending…" moment during which "Edit" or "Send now" are possible. Misheard words can be fixed before sending.
4. **Silence handling:** if the candidate says nothing for ~20 s after the interviewer finishes, a **canned** spoken nudge ("Take your time — I'm listening") plays, with **no LLM call**; after a second silence it offers to repeat the question (also canned).
5. **Interruptions:** default is turn-taking (the microphone is off while the interviewer speaks, which avoids echo). An optional "allow interrupting (use headphones)" setting listens during speech and stops the speech when the candidate starts talking.
6. **Coding round:** voice keeps working beside the editor; while a submitted solution is being reviewed the mic pauses, as the chat does.
7. **Always a way out:** if speech recognition is unavailable or permission is denied, the room works exactly as today by typing.

## 3. Steps

**8.1 `VoiceIO` layer** — `lib/voice/` : feature detection, `SpeechRecognizer` (continuous, interim results, restart on the browser's silent timeouts, error mapping: not-allowed, no-speech, network, audio-capture), `SpeechSynthesizer` (voice choice persisted, rate, chunking long replies by sentence so "stop" is instant, `speaking` events), pure silence/endpointing logic (`useUtteranceBuffer`) unit-tested with a fake clock.
**8.2 UI** — voice toggle, mic/speaking indicator, live captions, "Sending in…" with Edit/Send now, silence-length and "allow interrupting" settings (stored per browser), permission/unsupported/denied states, accessible labels and no autoplay surprises (speech starts only after a user gesture).
**8.3 Integration** — hooks into `InterviewRoomView` (reply spoken after each turn and after the code-review reaction; mic pauses while sending or reviewing; nudges on silence; clean teardown on leave/complete).
**8.4 Backend** — none required. Optional small item: the interviewer prompt gains a "spoken style" line (short sentences, no lists or markdown) so replies sound natural — one prompt version bump with the usual tests.
**8.5 Tests** — endpointing/silence logic and the recognizer/synthesizer wrappers against fakes; `tsc`, `eslint`, `next build`; a short manual checklist for the owner (Chrome and Edge; headphones vs speakers; Firefox fallback).

## 4. Honest limits (to be verified by the owner on real hardware)
- Recognition accuracy depends on the browser's recognizer, accents and the microphone; punctuation is minimal. The edit-before-send step is the safety net.
- The free system voices are less natural than Gemini's. They are free and unlimited.
- Without headphones, an open mic during speech can pick up the interviewer; hence turn-taking by default.
- Chrome's recognizer needs internet and sends audio to Google; this is shown to the user before first use.
- Mobile Safari support is partial; it falls back to typing.

## 5. Needed from the owner (status 2026-10-04: the approach and defaults were decided and built; the hands-on test is open)
1. Approval of this approach (browser voice now, premium voice later if wanted).
2. Which browsers you will use to test (Chrome/Edge assumed).
3. Whether replies should be **spoken by default** when voice is supported, or only after the candidate turns voice mode on (suggested: the candidate turns it on once, remembered afterwards).
