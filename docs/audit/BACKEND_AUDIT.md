# CyntraAI Backend Audit (apps/api, final whole-project audit, backend partition)

Scope: everything under `apps/api` except `migrations/` (read only where a contract needed it). Read-only audit; this file is the only thing written.
Method: every `.py` file under `app/` and `scripts/` was read in full; tests were read structurally (names, fakes, conftests, selected bodies) and by targeted greps; the suite was run; small python probes were used to confirm behaviours. No live provider was called, no script in `scripts/` was run, `.env` was not read.

## 1. Summary

| Item | Result |
|---|---|
| Files inventoried | `app/`: 117 `.py` (15 empty `__init__`, 3 `__init__` with code, 99 modules, 8,687 lines); `scripts/`: 9; `tests/`: 71 `.py` (+ `openapi_snapshot.json`); plus `.env.example`, `requirements.txt`, `requirements-dev.txt`, `pytest.ini` |
| Test run (`venv/Scripts/python.exe -m pytest -q`) | **605 passed, 1 skipped, 14 warnings in 12.71 s** (606 collected). The skip is `test_recorded_fixtures` (needs `tests/fixtures/gemini/*`, which does not exist: no live-recorded provider fixture has ever been captured). |
| Warnings | 2 DeprecationWarnings (gotrue, anyio alias), 3x python-jose `utcnow()`, 2x `RuntimeWarning: coroutine 'aclose' was never awaited` in the client-disconnect tests (see BE-M8) |
| `pip check` | No broken requirements |
| Prompt placeholders | All 11 templates checked with `string.Formatter`: every `.format()` call supplies exactly the placeholders present; JSON braces are correctly doubled |
| LLM task names | Used: `chat, interview, feedback, extract, summarize, judge, report` (+ `embed`, never model-looked-up). All present in `MODELS` for gemini/claude/groq and in `TIMEOUTS`. `validate` is used by the adapters' `validate()` and is present |
| Routers | All 10 routers registered in `app/main.py`; every route reaches an existing service/db function |
| Settings | All 10 settings are read somewhere; every one is in `.env.example` |
| Secret scan | No real key-like strings in `app/`, `scripts/`, `tests/` (only synthetic test keys). `.env` is not tracked by git |

Overall: the backend is in good shape. Layering is clean (only `app/db` touches Supabase; enforced by a test), every router is user-scoped, privileged routes check roles in the service layer, errors use one envelope, long work is jobs-with-heartbeat, and prompt-injection defences are applied at every prompt construction point. **No CRITICAL defect was confirmed.** One HIGH item is data/seed related (the coding round silently degrades if the question bank lacks questions for a type). The rest are MEDIUM/LOW robustness, product-accuracy and hygiene items.

Top findings (details in section 3):

- **BE-H1 (HIGH, seed/data dependent)** The starter loader gives 2 coding + 1 webd questions and 0 sde; `webd` needs 2 and `sde` needs 1. With a thin bank `webd` problem 2 repeats problem 1 and can never be submitted (`already_submitted`), and `sde` has no coding round at all, silently.
- **BE-M1** An empty requirements extraction is cached for 1 hour, so one flaky model reply locks the user out of that JD with a 422 for an hour (no LLM retry possible).
- **BE-M2** Boot recovery fails every active job in the table, not just this process's: any rolling deploy or second instance kills live setups/reviews/reports of the other instance.
- **BE-M3** Job/submission state-machine gaps: `mark_succeeded/mark_failed` are unguarded, the review's single-submit claim happens before the stale-job path can run, and there is no periodic stale sweep.
- **BE-M4** `RequirementsOut.title` / `experience_level` are neither sanitised nor capped and are put unwrapped into the feedback prompt and saved in history.
- **BE-M5/M6** ATS semantic calibration (`LOW/HIGH`) is still a placeholder (40% of the composite), and model IDs/`thinkingLevel` have never been exercised live.
- **BE-M7** Resume download reads the whole S3 object into memory before the 500 KB check; PDF parsing has no page cap.
- **BE-M8** Chat disconnect cleanup (usage + saving the partial reply + releasing the in-flight lock) depends on async-generator GC finalisers, not explicit `aclose`.
- **BE-M9** Streaming never waits out a short per-minute 429 and Groq/Claude quota kinds are never classified.
- **BE-M10** Report overall score ignores a bad code verdict when the model returns `null` for `coding_quality`.

## 2. Complete file table

Legend for "Tests": I = integration (`tests/integration`), U = unit, N = none found. Issue IDs refer to section 3.

### 2.1 app/core

| Path | Purpose | Used by | Tests | Issues |
|---|---|---|---|---|
| app/main.py | FastAPI app, router registration, lifespan (config validation, boot job recovery, report sweeper, drain), CORS, `/health`, `/ready`, `/health/authenticated` | uvicorn; tests (`app`) | I (all flows), U test_auth_flow (`/ready`, `/health`); lifespan itself NOT exercised (only `_recover_jobs`) | BE-M2, BE-L12, BE-L18 |
| app/core/config.py | pydantic Settings, `config_problems`, `validate_config` | main, security, db, storage | U test_config | BE-L12 |
| app/core/context.py | request-id/user-id contextvars | middleware, security, jsonlog, errors | U test_error_envelope | none |
| app/core/db.py | cached Supabase client | all `app/db/*` | conftest fakes it | none |
| app/core/errors.py | `AppError`, unified envelope, handlers | everywhere | U test_error_envelope | BE-L16 |
| app/core/ids.py | `UuidStr` validator | all routers/models | I test_audit_regressions, test_interview_flow | BE-L3 |
| app/core/jobs.py | job runner: launch, semaphore (6), stale, recovery | interviews, coding, reports, main | I test_jobs_flow | BE-M2, BE-M3 |
| app/core/background.py | fire-and-forget tasks with per-key dedupe, drain | interviews, rag, jobs | U test_background | BE-L10 (stale docstring) |
| app/core/jsonlog.py | JSON log formatter | main | U test_error_envelope | none |
| app/core/middleware.py | pure-ASGI request id, access log, catch-all 500 | main | U test_error_envelope | none |
| app/core/pagination.py | `page_params`, `large_page_params` | routers | I test_pagination | none |
| app/core/security.py | Fernet key encrypt/decrypt/rotate, JWT (HS256 + JWKS ES256/RS256), `get_current_user` | every router | U test_security, I test_auth_flow | BE-L13, BE-L14 |
| app/core/storage.py | boto3 S3 client, `download_bytes` | rag.service | I test_rag_flow (faked) | BE-M7 |
| app/core/throttle.py | per-user fixed-window throttle + `limited()` dependency | ats, rag, keys, interviews, coding, reports routers | U test_throttle | none |

### 2.2 app/db (the only Supabase layer)

| Path | Purpose | Used by | Tests | Issues |
|---|---|---|---|---|
| app/db/__init__.py | package docstring | - | U test_architecture | none |
| app/db/base.py | `run()` = `asyncio.to_thread` | all db modules | indirect | BE-L19 (thread pool) |
| app/db/ats_history.py | ATS history RPC + list/get/delete | ats.service | I test_pending_features | none |
| app/db/chat.py | conversations/messages; `append_exchange` RPC | chat.service | I test_chat_flow | `append_message` DEAD (BE-L7) |
| app/db/interviews.py | interviews + transcripts, `append_turns` RPC | interviews, coding, reports, main | I test_interview_flow | `next_turn_index` DEAD (BE-L7); BE-L9 |
| app/db/jobs.py | jobs table ops | core.jobs, interviews, coding, jobs router | I test_jobs_flow | BE-M3 |
| app/db/keys.py | provider keys, notifications | keys, gateway, ats, rag, interviews | I test_keys_flow | BE-L13 |
| app/db/maintenance.py | bulk reads/writes for owner scripts | scripts/reembed, rotate_keys | U test_embedding_cache_and_reembed (reembed only) | rotate path untested |
| app/db/questions.py | roles, permissions, question bank, `match_question_bank_v2` | question_bank, team, interviews, coding | I test_question_bank etc. | none |
| app/db/readiness.py | `/ready` DB probe | main | I test_auth_flow | none |
| app/db/reports.py | reports CRUD, purge | reports.service | I test_reports_flow | BE-L11 (delete+insert not atomic) |
| app/db/resumes.py | resumes, `replace_chunks` RPC, `match_resume_chunks_multi` | rag, ats, interviews | I test_rag_flow, test_ats_flow | none |
| app/db/submissions.py | code submissions | coding, reports, main | I test_coding_flow | BE-M3 |
| app/db/team.py | team lists, role/permission writes | team.service | I test_pending_features (via fake) | BE-L11 |
| app/db/usage.py | usage RPC + read | llm.usage, llm.router | U test_usage | none |

### 2.3 app/llm

| Path | Purpose | Used by | Tests | Issues |
|---|---|---|---|---|
| app/llm/gateway.py | single entry for complete/stream/embed: cooldown, limiter, retry, failover, usage | chat, ats, rag, interviews, coding, reports, question_bank | U test_gateway, test_gateway_m2, test_structured_output; I test_gateway_flow | BE-M9, BE-L15 |
| app/llm/budget.py | token estimate, truncate, fit_to_budget, trim_to_sentence | many | U test_llm_foundation | none |
| app/llm/completion.py | `Completion` dataclass | gateway | U | none |
| app/llm/json_utils.py | `extract_json` | gateway, scripts | U test_structured_output | none |
| app/llm/keystate.py | key fingerprint, cooldowns, Pacific-day helpers | gateway, usage | U test_gateway_m2, test_llm_foundation | BE-L4 |
| app/llm/limiter.py | per-key sliding-window queue limiter | gateway | U test_limiter | unused import HTTPException (BE-L7) |
| app/llm/models.py | task->model, timeouts, Gemini thinking traits, embedding constants | adapters, gateway | U test_llm_foundation | BE-M6, BE-L10 |
| app/llm/options.py | `LLMOptions`, `Usage` | everywhere | U | none |
| app/llm/prompts/ats.py | requirements + feedback prompts | ats | U | BE-M4 |
| app/llm/prompts/coding.py | code review system prompt | coding | I test_coding_flow | none |
| app/llm/prompts/interview.py | setup/turn/summary prompts, goals | interviews | I test_interview_flow | none |
| app/llm/prompts/report.py | report prompt | reports | I test_reports_flow | none |
| app/llm/prompts/resume.py | digest prompt | rag | I test_rag_flow | none |
| app/llm/router.py | `GET /usage` | main | U test_usage | BE-L17 (no response model) |
| app/llm/schemas.py | `RequirementsOut`, `SetupOut` coercing schemas | ats, interviews, coding | U test_structured_output, test_requirements_extractor | BE-M4 |
| app/llm/ttl_cache.py | tiny TTL cache | gateway, requirements | U test_ttl_cache | none |
| app/llm/untrusted.py | wrap/neutralize/sanitize/leak filter/attach_context | all prompt builders | U test_prompt_injection | BE-M11, BE-L6 |
| app/llm/usage.py | usage recording | gateway | U test_usage | BE-L15 |
| app/llm/__init__.py, prompts/__init__.py | empty | - | - | none |

### 2.4 app/providers, app/rag

| Path | Purpose | Used by | Tests | Issues |
|---|---|---|---|---|
| app/providers/base.py | adapter ABC, message types, error taxonomy | all | U | `embed()` base method only used in tests |
| app/providers/registry.py | adapter singletons | gateway, keys, rag.embeddings | tests monkeypatch it | none |
| app/providers/gemini.py | Gemini REST adapter (chat, stream, embed, validate, thinking self-heal, error mapping) | registry | U test_gemini_adapter (28) | BE-M6, BE-L20 |
| app/providers/claude.py | Anthropic adapter | registry | U test_claude_groq_adapters | BE-M6, BE-M9 |
| app/providers/groq.py | Groq adapter | registry | U test_claude_groq_adapters | BE-M9 |
| app/rag/embeddings.py | truncating wrapper over Gemini embeddings | gateway | U test_rag_embeddings | `embed_text` DEAD (tests only) |
| app/rag/chunking.py | v1 fixed-window chunker | tests/eval harness only | U test_chunking, rag_eval | ORPHAN in production (BE-L7) |
| app/rag/resume_chunker.py | v2 section-aware chunker | rag.service | U test_resume_chunker (16), rag_eval | BE-L21 |
| app/rag/models.py | `ProcessResumeResponse` | rag router | I | none |
| app/rag/parsing/{__init__,pdf,docx}.py | text extraction | rag.service | U test_parsing | BE-M7 |
| app/rag/retrieval.py | re-exports two db functions | ats, interviews | indirect | thin alias module |
| app/rag/router.py | `POST /rag/resumes/{id}/process` | main | I test_rag_flow | none |
| app/rag/service.py | download, parse, chunk, embed, atomic replace, digest | rag router | I test_rag_flow (15) | BE-M7, BE-M12 |
| app/rag/__init__.py | empty | - | - | none |

### 2.5 app/ats, chat, keys, jobs, team

| Path | Purpose | Used by | Tests | Issues |
|---|---|---|---|---|
| app/ats/router.py | score + history endpoints | main | I test_ats_flow, test_pending_features | none |
| app/ats/service.py | score pipeline + history | router | I, U test_ats_service | BE-M1 |
| app/ats/requirements_extractor.py | JD -> requirements, 1h cache | ats.service, interviews | U test_requirements_extractor | BE-M1 |
| app/ats/semantic.py | calibrated semantic coverage | ats.service | U test_ats_semantic (18) | BE-M5 |
| app/ats/scorer.py | keyword/format/composite scores | ats.service | U test_scorer | `missing_terms` DEAD (tests only) |
| app/ats/feedback.py | feedback LLM call | ats.service | I | BE-M4 |
| app/ats/models.py | request/response models | router | snapshot | none |
| app/chat/router.py | conversations + streaming reply | main | I test_chat_flow (21) | BE-M8 |
| app/chat/service.py | history window, streaming, persistence | router | I, U test_chat | BE-M8, BE-L2 |
| app/chat/models.py | models | router | snapshot | BE-L2 |
| app/keys/router.py, service.py, models.py | BYO key submit/list/delete with validation | main | I test_keys_flow, U test_keys_submit | BE-L13 |
| app/jobs/router.py | `GET /jobs/{id}` | main | I test_jobs_flow | none |
| app/team/router.py, service.py | owner-only team management | main | I test_pending_features | BE-L11 |

### 2.6 app/interviews, coding, reports

| Path | Purpose | Used by | Tests | Issues |
|---|---|---|---|---|
| app/interviews/router.py | question bank CRUD + lifecycle endpoints | main | I (34+ tests) | none |
| app/interviews/service.py | setup job, turns, complete/abort/delete | router, coding, main | I test_interview_flow, test_jobs_flow, test_pending_features, U test_interview_service/diet | BE-H1, BE-M2, BE-L9 |
| app/interviews/question_bank.py | admin CRUD with permission check + embedding | router | I test_question_bank | none |
| app/interviews/question_selection.py | MMR diversified pick | service | U test_question_selection, I | none |
| app/interviews/orchestrator.py | phase by elapsed time | service, coding, reports | U test_orchestrator | none |
| app/interviews/summarizer.py | rolling summary | service | U test_interview_diet | BE-L22 |
| app/interviews/models.py | request/response models | router | snapshot | duplicate import (BE-L7) |
| app/interviews/types/{__init__,behavioral,case_study,coding,hr,ml_ai,sde,system_design,webd}.py | interview type configs | service | U | BE-H1 |
| app/interviews/voice/__init__.py | empty package, nothing in it | nothing | N | ORPHAN (BE-L7) |
| app/coding/router.py | problem + submissions endpoints | main | I test_coding_flow (16) | none |
| app/coding/service.py | claim submit, review job, leak filter | router | I | BE-M3, BE-M11 |
| app/coding/schemas.py | `ReviewOut` | service | I, judge_eval | none |
| app/reports/router.py | report endpoints | main | I test_reports_flow (15) | none |
| app/reports/service.py | report job, assemble, expiry, sweeper | router, main | I, U test_reports_unit | BE-M10, BE-L11 |
| app/reports/evidence.py | evidence pack | service | U test_reports_unit | none |
| app/reports/scoring.py | caps, overall, quote check | service | U test_reports_unit | BE-M10 |
| app/reports/schemas.py | `ReportOut` (model proposal) | service | U, I | BE-L7 (name clash) |

### 2.7 apps/api/scripts (never run by this audit)

| Path | Purpose | Notes |
|---|---|---|
| scripts/__init__.py | empty | |
| scripts/llm_smoke.py | owner-run live Gemini/Groq/Claude smoke, records fixtures | docstring says "not imported by the test suite" but `tests/test_recorded_fixtures.py` imports it (BE-L10) |
| scripts/rag_eval_live.py | calibrate ATS LOW/HIGH with real embeddings | unused import `statistics`; imports `tests.rag_eval.golden` |
| scripts/judge_eval_live.py | live accuracy of the code reviewer | imports private `_review_messages`, `_REVIEW_OPTIONS` |
| scripts/report_eval_live.py | live report sanity check | imports private `_messages`, `_OPTIONS` |
| scripts/load_starter_questions.py | seeds 3 starter problems | BE-H1; only first 500 existing rows checked; embeds without the 1,800-token truncation the app applies |
| scripts/reembed.py | re-embed stale vectors | covered by U tests of `reembed_rows` only |
| scripts/rotate_keys.py | re-encrypt stored keys | no test |
| scripts/update_openapi_snapshot.py | rewrites snapshot | used by test_openapi_snapshot |

### 2.8 Config / data files

| Path | Verdict |
|---|---|
| .env.example | Complete for the app (10 vars). Scripts' env vars (`GEMINI_API_KEY` etc.) are documented only in script docstrings |
| requirements.txt / requirements-dev.txt / pytest.ini | See section 7 / 6 |
| tests/openapi_snapshot.json | 39 operations, 40 schemas; see BE-L17 |

### 2.9 tests/ (71 files; counts are `def test_` per file)

Integration (`tests/integration`, FastAPI app + in-memory fake Supabase + fake adapters): conftest.py, fakes.py (infrastructure); test_ats_flow 14, test_audit_regressions 7, test_auth_flow 12, test_chat_flow 21, test_coding_flow 16, test_gateway_flow 11, test_interview_flow 34, test_jobs_flow 14, test_keys_flow 13, test_pagination 3, test_pending_features 14, test_question_selection_flow 5, test_rag_flow 15, test_reports_flow 15.
Unit (`tests/`): conftest.py, helpers.py; test_architecture 3, test_ats_semantic 18, test_ats_service 6, test_audit_fixes 4, test_background 4, test_blocked_replies 2, test_chat 8, test_chunking 5, test_claude_groq_adapters 15, test_config 9, test_embedding_cache_and_reembed 9, test_error_envelope 6, test_gateway 19, test_gateway_m2 19, test_gemini_adapter 28, test_interview_diet 12, test_interview_service 5, test_keys_submit 2, test_limiter 6, test_llm_foundation 13, test_openapi_snapshot 2, test_orchestrator 6, test_parsing 4, test_prompt_injection 16, test_question_bank 6, test_question_selection 7, test_rag_embeddings 3, test_rag_service 8, test_recorded_fixtures 3 (1 skipped), test_reports_unit 11, test_requirements_extractor 6, test_resume_chunker 16, test_scorer 9, test_security 7, test_structured_output 5, test_throttle 5, test_ttl_cache 1, test_usage 5.
Eval fixtures: judge_eval (golden.py, test_golden 4), rag_eval (fake_embedder, golden, harness, report, v2_pipeline, test_harness 7), report_eval (golden.py, test_golden 3); empty `__init__.py` in tests/, integration/, judge_eval/, rag_eval/, report_eval/.
Three tests have no `assert` (they assert "does not raise"): test_usage `test_a_bookkeeping_failure_never_breaks_the_users_request`, test_jobs_flow `test_recovery_survives_a_database_error`, judge_eval `test_a_reviewer_answer_parses_with_the_real_schema`. Acceptable.

## 3. Findings

All confirmed by reading code (and, where noted, a probe). Severity: no CRITICAL; one HIGH; the rest MEDIUM/LOW.

### HIGH

**BE-H1 Coding round silently degrades when the question bank is thin (seed dependent).**
Files: `scripts/load_starter_questions.py:32-62`, `tests/judge_eval/golden.py` (PROBLEMS: 2 `coding`, 1 `webd`, 0 `sde`), `app/interviews/types/{webd,sde}.py` (`QUESTION_COUNT` 2 and 1), `app/interviews/service.py:138-154,199`, `app/coding/service.py:92`.
What: `_select_questions` returns whatever exists (no error). `selected_question_ids` is then shorter than the phases. `index = min(question_index_for(phase), len(ids)-1)`, so for `webd` with one bank question, problem 2 resolves to the same question id as problem 1; `create_submission` hits the partial unique index and the user gets `already_submitted`. For `sde` with no questions `in_problem` is false and `_problem_phase` raises `not_a_coding_phase`: there is no coding round and no message explaining why (the editor simply never activates).
Scenario: owner runs the loader, starts a Web Dev or SDE interview, never gets two problems / any problem.
Fix: seed at least 2 `webd` and 1-2 `sde` questions (and a few more `coding` ones so repeats are avoided); make setup fail (or warn the user via the job result) when `len(selected) < config.question_count` for a coding-platform type; do not map problem 2 onto problem 1. Needs verification: the actual contents of the live `question_bank` table.

### MEDIUM

**BE-M1 Empty requirements are cached for an hour.**
`app/ats/requirements_extractor.py:61-62` caches `result` even when both lists are empty; `app/ats/service.py:44-49` then raises 422 "Couldn't find any skills". A retry within the TTL hits the cache and never calls the model again (also changes `cached_requirements` for interviews).
Scenario: model returns `{"must_have": []...}` once (JSON mode glitch) -> user retries the same JD for an hour and gets the same 422.
Fix: only cache when `must_have or nice_to_have` is non-empty.

**BE-M2 Boot recovery fails every active job, not only this process's.**
`app/core/jobs.py:141-149`, `app/db/jobs.py:115-129`, `app/main.py:33-46`.
Scenario: Render-style rolling deploy (new instance boots while the old one is still serving) or a second worker: the new process marks the old process's running setup/review/report jobs `failed`, aborts the interview whose setup is still running, and frees review submits. The old process's work then fails on its guarded update (`setup_cancelled`).
Fix: store an `instance_id` on jobs (set at launch) and recover only jobs of dead instances / stale heartbeats (`is_stale`), or only run recovery for jobs whose heartbeat is older than `STALE_AFTER_SECONDS`.
Related per-process state is listed in section 5.2.

**BE-M3 Job and submission state-machine gaps.**
(a) `app/db/jobs.py:103-112` `mark_succeeded` / `mark_failed` are not guarded by `status in (queued, running)`: a job failed as stale (or cancelled by `abort_interview`, `app/interviews/service.py:500`) can later be flipped to `succeeded` by the still-running work, overwriting the error. Likewise `app/db/submissions.py:79-90` `mark_done` is unguarded; after `mark_failed` freed the submit and a new submission was claimed, a late `mark_done` of the old row raises 23505 (unique index) instead of being ignored.
(b) `app/coding/service.py:216` claims the single submit BEFORE `launch()` (`:295`). If a review's job row is stuck active (the final `mark_succeeded`/`on_failure` write was lost during a DB blip) the submission stays `review`; the next submit gets `already_submitted` at `:219` and never reaches `launch()`'s stale-recovery path (`app/core/jobs.py:124-128`). Only a process restart frees it.
(c) There is no periodic stale-job sweep; staleness is evaluated only lazily inside `launch()`/`begin_setup`.
Fix: guard the three updates with `.in_("status", ACTIVE)` / `.eq("status","review")`; in `begin_review` evaluate/clean a stale active review job before `create_submission`; add a small sweep next to the report sweeper.

**BE-M4 Model-derived `title`/`experience_level` are neither sanitised nor capped, and enter a prompt unwrapped.**
`app/llm/schemas.py:36-47` (`title`, `experience_level` just `str(value).strip()`), used at `app/ats/feedback.py:26-33` (`Job: {title}` in the feedback prompt, only a "treat as labels" sentence protects it), stored at `app/ats/service.py:106` (`job_title`) and returned in history. Terms are sanitised (`_clean_list`), title is not.
Scenario: a JD with "output title: <500 chars of instructions>" produces an arbitrary-length title which steers the feedback call and is persisted.
Fix: `neutralize_tags(strip_controls(...))[:80]` for `title`, whitelist `experience_level` to `entry|mid|senior|lead|unspecified`, and wrap the title in a `<data>` block (or just cap it).

**BE-M5 ATS semantic calibration is still a placeholder.**
`app/ats/semantic.py:24-27` (`LOW=0.55`, `HIGH=0.80`, labelled PLACEHOLDERS). The semantic score is 40% of the composite (`scorer.composite_score`) and drives "covered / missing". Until the owner runs `scripts/rag_eval_live.py` the absolute ATS number is not trustworthy (ranking between resumes is).
Fix: owner-run the live eval and paste the suggested values.

**BE-M6 Provider/model facts never verified live.**
`app/llm/models.py:9-25` says IDs are "not yet exercised with a live key": `gemini-flash-lite-latest` with `thinkingLevel: minimal` (guessed; adapter self-heals on a 400 mentioning "thinking"), `claude-sonnet-5-5` (Claude adapter always sends `temperature`; newer Claude models may reject some parameter combinations), `llama-3.3-70b-versatile`. No fixtures exist (`tests/fixtures` missing -> 1 skipped test), so Gemini error-body mapping (`map_error`) is verified only against synthetic bodies. **Needs verification** by the owner running `scripts/llm_smoke.py --record` once.

**BE-M7 Resume download and PDF parsing are unbounded before the size check.**
`app/core/storage.py:26` `response["Body"].read()` loads the whole object; `app/rag/service.py:110` checks `len(file_bytes) > 500KB` only afterwards. `app/rag/parsing/pdf.py:8-12` has no page cap (a small compressed PDF can hold many pages), and runs in the default thread pool, holding the GIL.
Scenario: an object larger than expected under the user's own `resumes/{uid}/` prefix (only the web route should create these, so exploitability is low) is fully loaded into memory.
Fix: use `ContentLength` from `get_object` (reject > 500 KB before reading) or `Body.read(limit+1)`; cap pages (e.g. 10) and per-page chars in `extract_text_from_pdf`.

**BE-M8 Chat disconnect handling relies on async-generator GC finalisers.**
`app/chat/router.py:72-82`: the first chunk is pulled manually and `body_stream()` iterates `replies` without closing it; `app/chat/service.py:72-107` and `app/llm/gateway.py:598-613` put the partial-reply save, usage recording and `_replies_in_flight.discard` in `finally` blocks. When Starlette cancels `body_stream()` the nested generators are only closed when the event loop's asyncgen finaliser runs after garbage collection. The two `RuntimeWarning: coroutine ... 'aclose' was never awaited` in `test_chat.py::test_a_client_disconnect_mid_reply_saves_what_the_user_saw` and `test_gateway_m2.py::test_usage_is_recorded_when_the_consumer_disconnects_mid_stream` are this exact mechanism. In CPython it normally works promptly; it is nondeterministic under reference cycles, and a client that disconnects between the first-chunk pull and the first iteration leaves the conversation locked (409 `reply_in_progress`) until the generator is collected.
Fix: wrap with `contextlib.aclosing` / `try: ... finally: await replies.aclose()` in `body_stream()`, and in `stream_reply` close the gateway generator explicitly.

**BE-M9 Streaming never waits out a short per-minute 429; Groq/Claude quota kind never classified.**
`app/llm/gateway.py:569-571` (stream path just raises) vs the non-stream path's `rpm` wait (`:297-303`); `app/providers/groq.py:52-53` and `app/providers/claude.py:79-80` always create `ProviderRateLimitError(kind="unknown")` (only Gemini parses `rpm`/`rpd`). Consequences: a Groq daily-token exhaustion is re-probed every 60 s; a 1-2 s RPM 429 on a chat with no backup key surfaces as `quota_exhausted` ("no backup key is configured").
Fix: parse Groq's `x-ratelimit-*`/message ("per day") and Claude's `anthropic-ratelimit-*` into `kind`; allow one short wait in `stream()` before the first chunk.

**BE-M10 Report overall ignores a bad code verdict if the model nulls `coding_quality`.**
`app/reports/service.py:155-175`, `app/reports/scoring.py:43-50`. `apply_caps` only lowers an existing score; if the model returns `coding_quality: null` although `facts` exist (result `incorrect`), the dimension disappears and the overall is computed from the others only.
Fix: when `cap is not None` and the score is None, set `coding_quality = cap` (or force a floor derived from `RESULT_CAP`).

**BE-M11 `neutralize_tags` mangles HTML/JSX-like code that the reviewer reads.**
`app/llm/untrusted.py:38,52-54` applied to code by `wrap()`. Probe: `<user-card></user-card> <data-table>` becomes `[tag removed][tag removed] [tag removed]`; any tag starting with `data|system|assistant|user|instruction(s)` (custom elements, `<data>`, `<user>` placeholders) is replaced. For `webd` interviews the reviewer then judges corrupted code.
Fix: for `candidate_code` only strip the exact delimiter forms (`<data kind=`, `</data id=`) or escape `<` as an entity rather than deleting.

**BE-M12 A failed resume digest is never retried.**
`app/rag/service.py:124-127` returns early on an unchanged `content_hash`, before the digest is scheduled (`:153`), although `_get_owned_resume` already loads `digest`. After one failed background digest (quota, outage) the resume has no digest forever; every interview start then pays an extra embedding call and RPC (`app/interviews/service.py:193-208`).
Fix: if `digest` is empty on the early-return path, schedule `_store_digest` too.

### LOW

**BE-L1 No global request-body size limit.** Uvicorn/FastAPI accept arbitrarily large JSON; only per-field `max_length`s protect. Add a body cap (proxy or tiny ASGI middleware).
**BE-L2 Unbounded / whitespace inputs.** `app/chat/models.py:9` `CreateConversationRequest.title` has no `max_length`; `:13` `RenameConversationRequest.title` accepts whitespace-only, which `chat/service.py:30` then strips to an empty title; chat `content` (`:32`) accepts whitespace-only (Claude rejects blank text blocks -> 502).
**BE-L3 `UuidStr` accepts forms Postgres rejects.** `app/core/ids.py:7-9`: `UUID("urn:uuid:...")` is valid in Python, invalid in Postgres -> `22P02` -> generic 500 instead of 422.
**BE-L4 DST error in `seconds_until_pacific_midnight`.** `app/llm/keystate.py:27-28`: both datetimes share one `ZoneInfo`, so subtraction is wall-clock. Probe: on 2026-03-08 it returned 23.5 h (true 22.5 h) and on 2026-11-01 23.5 h (true 24.5 h). Cooldown off by 1 h twice a year. Use UTC arithmetic.
**BE-L5 `append_interview_turns` does not check interview status** (`migrations/0021_atomic_turns.sql`, called from `interviews/service.py:442`, `coding/service.py:273`). A turn finishing after `/complete` (or after delete -> P0002 -> 500) is appended to a completed interview, after the report might already be generated.
**BE-L6 Leak filters are narrow.** `leaks_protected_text` needs 8 consecutive identical words (`untrusted.py:107`), so short or paraphrased solution fragments pass; the interview opening (`interviews/service.py:241`) and reports have no leak filter. By design but worth knowing. `summary` (neutral reviewer note) is fed to later turns and may mention correctness.
**BE-L7 Dead code / orphans / lint.** Production-dead: `app/rag/chunking.py` (v1 chunker, tests/eval baseline only), `rag/embeddings.py:30 embed_text`, `ats/scorer.py:62 missing_terms`, `db/chat.py:102 append_message`, `db/interviews.py:143 next_turn_index`, empty package `app/interviews/voice/`. Unused imports: `llm/limiter.py:5 HTTPException`, `scripts/rag_eval_live.py:19 statistics`. Duplicate import `app/interviews/models.py:4,7 UuidStr`. Name clash: `reports/schemas.ReportOut` vs `reports/router.ReportOut`. Duplicated helpers: `_parse` (reports/service.py:57, evidence.py:29), `_norm` (coding/schemas.py:19, reports/scoring.py:77), `_get_owned_resume` (ats/service.py:20, rag/service.py:71), the "primary Gemini key required" check (rag, ats, interviews with three different messages). `coding/service.py:17` imports private names from `interviews/service.py`.
**BE-L8 Product behaviours worth a decision.** `begin_setup` (`interviews/service.py:291-299`) silently returns an already-running setup for a different type/resume if one is active (double-click protection, but no signal). `abort_interview` (`:496-502`) returns `status: aborted` even if the guarded update lost a race and the interview just became `in_progress`. Interviews past their time box remain `in_progress` until the client calls `/complete` (no server auto-complete); reports require `completed`.
**BE-L9 Interview context gap.** Raw window is 5 rows (`MAX_RAW_TURNS_IN_CONTEXT - 1`) and the summary only appears after 8 unsummarised rows (`summarizer.py:19,33`), so for the 4th answer the first two rows (opening + first answer) are in neither the window nor a summary (the brief covers the role/resume only).
**BE-L10 Stale comments.** `core/background.py:7-8` ("the planned jobs table" - it exists), `llm/models.py:17-18` ("once those columns exist"), `scripts/llm_smoke.py:23` ("not imported by the test suite" - it is).
**BE-L11 Non-atomic two-step writes.** `db/reports.py:74-82` delete-then-insert (a failed insert loses the old report; acceptable because it is regenerable); `db/team.py:64-77` delete-then-insert of permissions (a failed insert leaves an admin with none); `team.list_*` read a single page of 200 (users beyond 200 vanish from the Team page).
**BE-L12 Config defaults.** `ENVIRONMENT` defaults to `development` (`core/config.py:27`): forgetting it in production exposes `/docs`, `/openapi.json` and does not run the localhost-CORS check. `SUPABASE_JWT_SECRET` is optional with no warning, but a legacy-HS256 project then rejects every token.
**BE-L13 Keys.** `keys/service.py:20-65` does not `strip()` the key (the web form does; an API client sending a trailing space/newline hits h11 `LocalProtocolError`, verified, which is mapped to a misleading 503 "temporarily unavailable"). `db/keys.py:16` writes `is_valid: True` always and nothing ever flips it (the column carries no signal).
**BE-L14 Auth hardening.** `security.py:62` `response.json()` can raise `ValueError` (not `httpx.HTTPError`) -> 500; `iss` is not verified; anonymous-sign-in tokens (`is_anonymous`) are accepted as users.
**BE-L15 Usage accounting.** Every completion is booked as `kind="chat"` (`gateway.py:412-419,606`), so the DB cannot split interview/ATS/report usage (only logs can); failed or cancelled attempts that the provider still counted are not recorded (`usage.requests` is only incremented on success); the usage RPC is awaited inline on every turn (~1 DB round trip of latency).
**BE-L16 Envelope vs OpenAPI.** Real 422 bodies use the custom envelope (`errors.py:75-84`) but the snapshot documents FastAPI's `HTTPValidationError`.
**BE-L17 OpenAPI oddities.** No `securitySchemes` (the token is a plain `authorization` header parameter, so Swagger "Authorize" cannot be used); `/usage`, `/health/authenticated`, `/ready` have no response models; the chat streaming route's response is untyped `application/json`; no error responses beyond 422 are documented.
**BE-L18 Missing proxy hints for streaming.** `chat/router.py:82` sets no `Cache-Control: no-cache` / `X-Accel-Buffering: no`, so a buffering proxy can defeat streaming.
**BE-L19 Thread-pool pressure.** All DB calls, S3 reads and PDF parsing share the default `asyncio.to_thread` executor (about `cpu+4` threads); six concurrent jobs plus requests can queue behind long PDF parses.
**BE-L20 Gemini streaming** `json.loads(payload)` (`providers/gemini.py:364`) on a malformed SSE line raises `ValueError` (not a `ProviderError`) -> generic 500 mid-stream.
**BE-L21 Chunker detail.** `resume_chunker.normalize_resume_text` (`:69-74`) drops any short line (<=60 chars) occurring 3+ times as "page furniture", which also deletes legitimate repeats such as a "Remote" location line under three jobs.
**BE-L22 Summary window** counts rows, not exchanges (8 rows = 4 exchanges); fine, but the constant name suggests turns.

### Needs verification (not confirmed from code)

- Live behaviour of all three providers (BE-M6): model IDs, `thinkingLevel`, Claude `temperature`, Groq free-tier TPM limits versus the ~8.5k-token report prompt.
- `pdfminer.six==20231228` (via `pdfplumber==0.11.4`) and `python-jose==3.3.0`: check current advisories (jose 3.3.0 has published CVEs fixed in 3.4.0; pdfminer.six has had a CMap-loading advisory fixed in a later release). Both parse/verify untrusted input.
- The deployment's rolling-deploy / multi-worker model (BE-M2) and Python runtime (code needs >= 3.11: `datetime.UTC`, `asyncio.timeout`, `fromisoformat` of PostgREST timestamps).
- Real PostgREST timestamp formats (variable fractional digits) for `_elapsed_minutes`; fine on 3.11+.

## 4. Per-feature verdict

| Feature | Verdict | Issues | Residual risk |
|---|---|---|---|
| Auth (JWT HS256 + JWKS ES256/RS256) | done | BE-L14 | low; alg-none, wrong aud/secret, expired, unknown kid, JWKS outage (503) all tested |
| Keys (encrypt, validate, failover, rotation) | done | BE-L13, BE-M9 | provider quota-kind parsing for Groq/Claude |
| Chat streaming | done | BE-M8, BE-M9, BE-L2, BE-L18 | disconnect cleanup is GC-driven |
| Resume upload processing (download, parse, chunker v2, embed, atomic replace) | done | BE-M7, BE-M12 | oversized object / PDF pages; digest not retried |
| ATS (requirements cache, semantic coverage, scoring, history) | partly | BE-M1, BE-M4, BE-M5 | uncalibrated semantic score; empty-requirements lock-out |
| Interviews: setup job, turns, summaries, time box, abort/delete | done | BE-M2, BE-M3, BE-L5, BE-L8, BE-L9 | rolling-deploy kill; no server auto-complete |
| Question selection and bank admin | done | BE-H1 | bank content |
| Coding round (claim, job, schema, leak filter, one-submit) | partly | BE-H1, BE-M3, BE-M11 | thin bank; stuck-review recovery needs restart |
| Reports (evidence, caps, quote check, expiry, purge) | done | BE-M10, BE-L11 | code verdict not enforced when model nulls it |
| Jobs runner (stale, guarded transitions, slots) | partly | BE-M2, BE-M3 | unguarded success/failure writes; no sweep |
| Team management | done | BE-L11 | 200-user page |
| Usage / limits (limiter, throttle, quota day) | done | BE-L4, BE-L15 | per-process only |
| Voice | no backend code (empty `interviews/voice` package); browser-side | BE-L7 | none for backend |
| Error envelope / logging | done | BE-L16 | none |

## 5. Checks, with verdicts

### 5.1 The eight requested checks

1. **Linkage: PASS.** Routers all registered; no route calls a missing function. Dead code is limited to BE-L7. Prompt placeholders verified programmatically. All task names are in `MODELS` and `TIMEOUTS`. `.env.example` matches `Settings`.
2. **Correctness: PASS with findings** (BE-H1, M1, M2, M3, M10, M12, L4, L5, L8, L9). Timezones: all stored times are aware UTC (`datetime.now(UTC)`), parsers accept `Z`, Pacific quota day is computed with `ZoneInfo`; only the DST subtraction is off (BE-L4). No un-awaited coroutines in production paths; background tasks are held in `_tasks`; semaphores/locks are released in `finally` (BE-M8 aside).
3. **Error handling: PASS.** Every raise maps to the envelope; provider taxonomy mapping is 429 quota / 503 overloaded or misconfigured / 504 timeout / 400 key_rejected / 422 blocked / 502 bad request or empty; unexpected exceptions become a generic 500 or a generic job error without leaking text. Startup recovery is wrapped so a DB hiccup cannot block boot; shutdown cancels the sweeper and drains background tasks (8 s). Gaps: BE-L14, BE-L20.
4. **Security: PASS with findings.** IDOR: every query is scoped by `user_id` or goes through an owned-row lookup first (chat, interviews, transcript, turns, coding, reports, ATS history, jobs, keys, rag, usage); admin/owner checks are in the service layer (question bank: owner or admin with `manage_question_bank`; team: owner only). Reference solution and verdict never appear in candidate-facing responses (`get_problem` returns only the question text; `get_review_material` is used only by the reviewer; the reviewer's `summary` reaches later turns as wrapped data; the stored verdict reaches the candidate only in the post-interview report, as `result/approach/issues/complexity`). Prompt injection: every prompt-building site was grepped (all `Message(...)` constructions): untrusted text is wrapped with a random boundary, derived text is sanitised before storage, replies pass `clean_reply` + leak filters; only BE-M4 (title) is a gap. Input limits exist on all user-facing request models except BE-L1/L2. Throttles: ats.score 6/min, rag.process 6, keys.submit 10, interviews.start 4, code.submit 6, reports.generate 3; unthrottled (bounded by the per-key limiter): chat send, turns, question-bank create. No SSRF surface (URLs come from config; storage key prefix and `..` checked). Logs carry request id and user uuid only; no key material is logged (provider error text is turned into generic messages). CORS is explicit-origin; docs are disabled in production (BE-L12 caveat).
5. **Performance: see section 6 table.**
6. **Tests: see section 8.**
7. **Dependencies: see section 7.**
8. **Quality: see BE-L7, BE-L16, BE-L17 and section 10.**

### 5.2 Per-process state that breaks with more than one worker/instance

`core/throttle.py:58` (throttle windows), `llm/limiter.py:89` (per-key RPM windows: N workers multiply the effective rate), `llm/keystate.py:69` (key cooldowns), `chat/service.py:57` (`_replies_in_flight`), `interviews/service.py:329` (`_turns_in_flight`), `core/background.py:16-17` (summary/digest dedupe), `core/jobs.py:34` (6-slot semaphore per process), `core/security.py:49-54` (JWKS cache), `llm/gateway.py:621` and `ats/requirements_extractor.py:29` (caches; the interview JD query benefits from the ATS cache only on the same process), `providers/gemini.py:63` (`_thinking_rejected`), boot recovery (BE-M2), the report sweeper (`main.py:60`, harmless duplicates).

## 6. Latency / cost table (sequential awaits on the hot paths)

DB = round trips to Supabase (each ~50-150 ms through `to_thread`), LLM = completion calls, EMB = embedding calls. Every gateway call also does one `provider_keys` read (+decrypt) and one usage RPC, included below.

| Path | Sequential DB trips | LLM | EMB | Worst-case time bound | Notes |
|---|---|---|---|---|---|
| Start interview (request) | 5 (active job, resume, key, insert interview, insert job) | 0 | 0 | ~0.5 s | returns 202 immediately |
| Start interview (job) | ~15 (mark_started, 3 progress, key+usage per call, asked ids, match RPC (x2 on shortage), chunks RPC if no digest, update, transcript, succeeded) | 1 (2 with JSON repair) | 1 (skipped for no-question types with a digest) | embed 70 s + 60-120 s | `STALE_AFTER` 420 s is comfortable |
| Interview turn | 6 (interview, phase update sometimes, reads wave, key, usage, append RPC) + 1 background read per turn | 1 (summary every ~4 exchanges, background) | 0 | deadline 60 s (25 s x2 + 10), typical 1-3 s | usage RPC is awaited inline (BE-L15) |
| Submit code (request) | 3 | 0 | 0 | ~0.5 s | |
| Code review (job) | ~10 | 1-2 (judge 45 s x2 + 10 each) | 0 | ~200 s | prompt ~5.6k tokens, output cap 1,000 |
| ATS score | ~9 (resume, key, extract key+usage, embed key+usage, match RPC, feedback key+usage, history RPC) | 2 (extraction cached 1 h per JD) | 1 (query vectors cached 1 h) | 60 s + 70 s + 40 s | 4 separate key lookups per request; one 12-rpm Gemini minute allows ~5 scores |
| Report | ~8 (+2 for delete+insert) | 1-2 (60 s x2 + 10 each) | 0 | ~260 s job | prompt <= ~8.5k tokens incl. 1,800 output |
| Resume process | ~6 (+ digest in background: key, usage, set) | 1 background (digest) | 1 (<= 60 chunks, one batch) | S3 + parse in thread; embed 70 s | download unbounded (BE-M7) |
| Chat message | 3 before first token (owned conv, history, key) + 2 after (usage, append RPC) | 1 streaming | 0 | TTFT + 60 s silence timeout | no overall stream deadline |

Cost controls present: token caps everywhere, query-vector cache, requirements cache, background priority in the limiter, summary every ~4 exchanges, digest reuse. N+1: none found (ATS coverage is one RPC for all terms; team list is one gather). Missing LIMITs: none on user paths (all lists paginated; `transcript()` is bounded by the interview). Cache sizes: query cache 500 x ~25 KB (about 12 MB), requirements cache 256, throttle/limiter evict idle users.
Cheap wins: cache the decrypted key per request (saves 2-4 DB trips on ATS/report), fire-and-forget the usage RPC (saves one round trip per LLM call), parallelise the two independent resume/key reads in `_validate_start`/`score_resume`.

## 7. Dependencies

`requirements.txt` vs imports: every import resolves to a pinned package; `postgrest` (imported directly by `db/jobs.py`, `db/reports.py`, `db/submissions.py`) and `starlette`, `h11`, `anyio` are only transitive pins (LOW). `tzdata` is correctly listed (Windows ZoneInfo). No unused pinned package. `pip check`: clean. The venv contains leftovers not in requirements (`google-ai-generativelanguage`, `google-api-python-client`, `google-auth`, `APScheduler`, `grpcio`, `protobuf`, `PyJWT`), so "works in venv" is not proof that a clean `pip install -r requirements.txt` works; test with a fresh venv.
Compatibility: fastapi 0.115.6 / starlette 0.41.3 / pydantic 2.10.3 / pydantic-settings 2.6.1 / uvicorn 0.32.1 are a consistent set; httpx is pinned to 0.27.2 for supabase 2.10 compatibility. Python 3.13.5 in the venv; code requires >= 3.11.
Risk notes: `python-jose==3.3.0` (known CVEs fixed in 3.4.0, `datetime.utcnow` deprecation warnings; PyJWT is already installed); `anthropic==0.40.0` and `groq==0.13.1` are ~10 months old relative to the configured models (a new model id is just a string, but typed stop reasons/new params are missing); `supabase==2.10.0` pulls the deprecated `gotrue`; `cryptography==43.0.3` is behind current; `pdfminer.six==20231228` (see needs-verification). None of these block testing.

## 8. Tests

Counts: 605 passed, 1 skipped, 606 collected, ~12.7 s. Coverage is broad (every router has integration tests with ownership, validation and failure paths; adapters, gateway, limiter, chunker, scorer, report maths and prompt-injection have focused unit tests; OpenAPI shape is pinned).

**Features / branches with no test found:** FastAPI `lifespan` (config validation at boot, sweeper start/cancel, drain with 8 s timeout); `core/storage.py` and real S3 errors (only a faked `download_bytes`); `scripts/rotate_keys.py`; `db/maintenance.py` rotate path; `db/team.py` (`replace_permissions` failure, `list_auth_users` paging); `_MAX_CHUNKS` truncation; production docs disabled (`docs_url=None`); `CORS` headers on streaming errors; JWKS `ValueError` path; `mark_succeeded`/`mark_failed` overwriting a stale/cancelled job (BE-M3); stuck-review-submission recovery; interview opening leak path; `ENVIRONMENT` unset behaviour; Groq/Claude quota-kind parsing (not implemented); streaming chat proxy headers; DST in `seconds_until_pacific_midnight`; concurrency between `/complete` and an in-flight turn; deleting an interview with an in-flight job; two `webd` problems with a one-question bank (BE-H1); large-body requests.
**Tests that assert little / are tightly coupled:** the three no-assert tests above; `test_architecture::test_every_db_query_on_a_user_owned_table_is_scoped_by_user_id` only counts `eq("user_id", ...)` substrings in three files; `test_a_client_disconnect...` passes while emitting the `aclose` RuntimeWarning (BE-M8); `FakeAdapter.default_reply` branches on task name, so a renamed task silently falls back to "Hello from the fake model."; RPC fakes re-implement SQL in Python (`record_ats_score`, `match_resume_chunks_multi` with a fixed similarity of 0.75/0.3, `match_question_bank_v2` with fixed 0.9), so the real SQL, vector math and ordering are not tested.
**Behaviours the app relies on that the fake Supabase (`tests/integration/fakes.py`) does not emulate:** foreign keys and ON DELETE CASCADE/SET NULL (deleting an interview does not remove transcripts/submissions/reports; deleting a resume does not null `interviews.resume_id`); unique constraints other than three hard-coded ones (`code_submissions` per problem, `jobs` active per kind, `interview_reports` per interview) - e.g. `provider_keys (user_id, provider, slot)`, `admin_permissions` unique, `roles`; check constraints and enums (only `interviews.type`/`question_bank.type` are validated; status enum values are not); column grants/RLS and the DB-enforced 3-resume limit trigger (migrations 0028/0029); `SECURITY DEFINER` and `search_path` of RPCs; transactions/row locks (RPCs are atomic by construction in Python); `updated_at`/default timestamps and real PostgREST timestamp formatting; `maybe_single` error variants beyond 0/2+ rows; PostgREST `count`, `range` semantics and 1000-row caps; Auth admin `list_users` paging; embeddings as `vector(768)` text round-trip; real `plainto_tsquery` stemming used by `kw_hit` (fake uses whole-word regex); statement/timeouts; concurrency (single-threaded list mutation).

## 9. OpenAPI / public API notes

39 operations. All create endpoints return 201/202 as expected; deletes 204; `POST /interviews/{id}/report` returns 202 even when `ready: true`. See BE-L16, BE-L17. Route order is correct (`/interviews/question-bank` registered before `/{interview_id}`). Paths like `/interviews/{id}/problem`, `/submissions`, `/report` come from other routers sharing the `/interviews` prefix, which is fine but undocumented.

## 10. Quality notes

Overly broad `except Exception` sites were each reviewed and are intentional and logged (`rag._make_digest`, `jobs._safe`, `main._recover_jobs`, `ats.service` history save, `usage.record`, `chat` append, `keys.submit_key` unknown error -> 502, `rag` download/parse -> 404/502/422). Magic numbers that could be settings: `MAX_CONCURRENT=6`, `STALE_AFTER_SECONDS=420`, per-endpoint throttle limits (inline in routers), `DEFAULT_RPM`, token caps, `_MAX_FILE_BYTES`, `REPORT_DAYS`. DB rows are plain dicts everywhere (no TypedDict/models), so a column typo is only caught at runtime; `report`/`resume` parameters in `_run_setup`, `_review_messages(config...)` are untyped. Naming: `InterviewProviderName` vs `ProviderName`; both `ReportOut`s.

## 11. Upgrades worth doing (prioritised)

1. Seed the question bank to cover `coding` (>= 6), `webd` (>= 4), `sde` (>= 3) and make setup/problem logic refuse (or warn) when fewer questions than `question_count` are available (BE-H1).
2. Run the owner-only live scripts once: `llm_smoke --record` (fixtures + model/thinking facts), `rag_eval_live` (paste LOW/HIGH), `judge_eval_live`, `report_eval_live` (BE-M5, BE-M6).
3. Instance-aware job recovery + guarded job/submission transitions + a periodic stale sweep; reorder `begin_review` so stale handling precedes the claim (BE-M2, BE-M3).
4. Do not cache empty requirement extractions; sanitise and cap `title`/`experience_level` (BE-M1, BE-M4).
5. Explicit `aclosing` of the chat stream chain and a streaming short-RPM wait; classify Groq/Claude quota kinds (BE-M8, BE-M9).
6. Bound S3 reads and PDF pages (BE-M7); upgrade `python-jose` (3.4.0+) or switch to PyJWT; refresh `pdfminer.six`.
7. Retry the digest on reprocess (BE-M12); enforce coding caps even when the model nulls the dimension (BE-M10); soften tag neutralisation for code (BE-M11).
8. Request-body size limit, `ENVIRONMENT` fail-closed in production, JWT `iss` check (BE-L1, BE-L12, BE-L14).
9. Reduce latency/cost: per-request key cache and non-blocking usage recording (section 6).
10. Housekeeping: delete dead code (BE-L7), fix stale comments (BE-L10), document `securitySchemes` and error responses in OpenAPI (BE-L17), add the missing tests listed in section 8 (lifespan, stale-job overwrite, `webd` thin bank, DST).
