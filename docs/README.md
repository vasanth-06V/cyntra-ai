# CyntraAI documentation index

Last reviewed 2026-10-04. Status key: **current** (kept in line with the code), **historical** (accurate for its date, kept as a record; read its banner), **superseded** (replaced by another document; do not follow), **point-in-time** (a dated snapshot; accurate on its date, not updated).

Start with `PRODUCT.md` for what the product is, and the STATE SNAPSHOT at the top of `PROJECT_DOCUMENTARY.md` for where the project stands.

| Document | What it is | Status |
|---|---|---|
| [PRODUCT.md](PRODUCT.md) | The single A-Z reference: features, architecture, API inventory, data model, decisions, what is verified live, known limitations, what remains, env vars | **current** (2026-10-04) |
| [PROJECT_DOCUMENTARY.md](PROJECT_DOCUMENTARY.md) | Chronological build journal (Action / Why / Result / Problems), with a current STATE SNAPSHOT (2026-10-04) at the top | **current** snapshot at the top; the log below it is **historical**; the older 2026-10-02 snapshot inside the log is **superseded** |
| [DEPLOY.md](DEPLOY.md) | Owner runbook: Supabase, Vercel, Render, env vars, verification, pause handling, rollback; lists the deployment files (all written; the Dockerfile has not been built yet) | **current**, draft for approval (nothing deployed yet) |
| [LAUNCH_CHECKLIST.md](LAUNCH_CHECKLIST.md) | Owner checklist for launch: secret rotation, demo sign-up removal, hardening, owner-run scripts, headers, monitoring, full manual walk-through | **current**, draft for approval |
| [FACTS.md](FACTS.md) | External facts the product depends on (hosting, Supabase, Gemini, Claude, Groq, browser voice, Monaco), each marked verified / measured / unverified / obsolete | **current** (2026-10-04) |
| [IMPLEMENTATION.md](IMPLEMENTATION.md) | The original end-to-end plan from 2026-09-27 (stack, schema, ten build phases) | **historical**, superseded by PRODUCT.md (banner at the top lists the changes) |
| [PILLARS_PLAN.md](PILLARS_PLAN.md) | Plan to harden the RAG, LLM and backend pillars (milestones M0-M4) | **historical**: completed; an Outcome section and a "Deferred / not delivered" list were added at the top |
| [PHASE7_PLAN.md](PHASE7_PLAN.md) | Coding round plan (rev 2: logic review, no execution) | **historical**: built and migration applied; status line and corrections updated |
| [PHASE8_PLAN.md](PHASE8_PLAN.md) | Voice plan (browser speech APIs) | **historical**: built, hands-on test pending |
| [PHASE9_PLAN.md](PHASE9_PLAN.md) | Reports plan (on demand, 7-day expiry) | **historical**: built and migration applied |
| [PHASE10_PLAN.md](PHASE10_PLAN.md) | Polish and deploy plan | **historical / partly open**: cleanup and polish done; Docker/Render files, real-Postgres CI and Playwright not built |
| [FRONTEND_GAPS.md](FRONTEND_GAPS.md) | Frontend functional gaps found on 2026-10-04 and their fixes (G01-G32, B01-B08), all marked done | **historical** (all items resolved) |
| [UI_REFRESH.md](UI_REFRESH.md) | Notes on the 2026-10-04 visual refresh (design tokens, primitives, motion) | **historical** (its test counts are those of its own round: 19 frontend tests then, 158 now) |
| [audit/BACKEND_AUDIT.md](audit/BACKEND_AUDIT.md) | Final backend audit (file table, findings, latency table, test gaps) | **point-in-time** (2026-10-04); most findings not yet fixed |
| [audit/FRONTEND_AUDIT.md](audit/FRONTEND_AUDIT.md) | Final frontend audit (route map, API contract matrix, findings, test gaps) | **point-in-time** (2026-10-04) |
| [audit/DB_DOCS_CROSSCUTTING_AUDIT.md](audit/DB_DOCS_CROSSCUTTING_AUDIT.md) | Final database, docs, CI, secrets, dependencies and operations audit | **point-in-time** (2026-10-04); its docs-correction list has been applied by this documentation pass |

Other places to look: `apps/api/.env.example` (backend variables), `apps/api/tests/openapi_snapshot.json` (the authoritative API shape, pinned by a test), the root `README.md` (overview and how to run), `apps/web/README.md` (web app notes) and `apps/web/.env.example`.
