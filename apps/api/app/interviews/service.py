import asyncio
import json
import logging
import re
from datetime import UTC, datetime, timedelta

from fastapi import status

from app.core import background
from app.ats.requirements_extractor import cached_requirements
from app.core import jobs as job_runner
from app.core.errors import AppError
from app.db import jobs as jobs_repo
from app.db import interviews as interviews_repo
from app.db import resumes as resumes_repo
from app.db import submissions as submissions_repo
from app.interviews import summarizer
from app.interviews.orchestrator import is_final_phase, minutes_remaining, phase_for_elapsed
from app.interviews.question_selection import select_questions
from app.interviews.types import get_config
from app.db.keys import get_key_row
from app.llm import gateway
from app.llm.budget import ensure_user_first, estimate_tokens, fit_to_budget, truncate
from app.llm.schemas import SetupOut
from app.llm.options import LLMOptions
from app.llm.prompts.interview import (
    SETUP_PROMPT,
    TURN_RULES_LINE,
    TURN_SYSTEM,
    context_block,
    goal_for,
    question_index_for,
)
from app.llm.untrusted import (
    NOTICE,
    SAFE_REDIRECT,
    attach_context,
    clean_reply,
    leaks_protected_text,
    new_boundary,
    sanitize_derived,
    wrap,
)
from app.providers.base import Message, MessageRole
from app.rag.retrieval import match_question_bank_v2, match_resume_chunks_multi

logger = logging.getLogger(__name__)

MAX_RAW_TURNS_IN_CONTEXT = 6
_OVERRUN_GRACE_MINUTES = 5

_SETUP_OPTIONS = LLMOptions(
    task="interview",
    json_mode=True,
    max_output_tokens=450,
    temperature=0.7,
    feature="interview_setup",
    prompt_id="interview.setup",
    prompt_version="2",
)
# trim_on_length: a reply cut off by the 160-token cap is shown as complete
# sentences, never a dangling half sentence.
_TURN_OPTIONS = LLMOptions(
    task="interview",
    max_output_tokens=160,
    trim_on_length=True,
    feature="interview_turn",
    prompt_id="interview.turn",
    prompt_version="2",
)

_JD_SETUP_TOKENS = 1200
_JD_FALLBACK_TOKENS = 300
_JD_QUERY_TOKENS = 400
_BRIEF_MAX_TOKENS = 300
_RESUME_FALLBACK_TOKENS = 400
_TURN_TOKEN_CAP = 120
_QUESTION_TOKEN_CAP = 400
_PROMPT_BUDGET_TOKENS = 2000
_MIN_HISTORY_TOKENS = 700  # always room for the last interviewer turn and a full-length answer


# Thin aliases onto the db layer. Kept as module-level names so the
# orchestration below reads naturally (and tests can replace one step).
_get_owned_interview = interviews_repo.get_owned_interview
_update_interview = interviews_repo.update_interview
_append_transcript = interviews_repo.append_transcript
_append_turns = interviews_repo.append_turns
_recent_turns = interviews_repo.recent_turns
_get_question_text = interviews_repo.question_text
_create_interview_row = interviews_repo.create_interview
_get_review_summary = submissions_repo.done_summary


async def _get_owned_processed_resume(user_id: str, resume_id: str) -> dict:
    return await resumes_repo.require_processed_resume(user_id, resume_id, "id, parsed_text, digest")


_OPENING_FIELD = re.compile(r'"opening"\s*:\s*"((?:[^"\\]|\\.)*)')
_FALLBACK_OPENING = "Hello, and thanks for joining. To start, could you tell me a little about yourself?"


def _salvage_opening(raw: str) -> str:
    """The model didn't return usable JSON (e.g. it was cut off by the output
    cap). Never show raw JSON to the candidate: pull the opening text out of
    it if present, otherwise use plain text as-is, otherwise a stock greeting."""
    raw = raw.strip()
    if not raw.startswith(("{", "```")):
        return raw or _FALLBACK_OPENING
    match = _OPENING_FIELD.search(raw)
    if match and match.group(1).strip():
        try:
            return json.loads(f'"{match.group(1)}"').strip()
        except ValueError:
            return match.group(1).strip()
    return _FALLBACK_OPENING


def _elapsed_minutes(interview: dict) -> float:
    started_at = datetime.fromisoformat(interview["started_at"])
    return (datetime.now(UTC) - started_at).total_seconds() / 60


def _jd_query(user_id: str, jd_text: str) -> str:
    """What the JD is searched as. The extracted requirements (free if an ATS
    check already ran on this JD) beat the raw posting, which is mostly
    boilerplate -- benefits, EEO text, company blurbs -- that drags questions
    toward the wrong topics."""
    requirements = cached_requirements(user_id, jd_text)
    if requirements:
        skills = ", ".join((requirements["must_have"] + requirements["nice_to_have"])[:12])
        if requirements.get("title") or skills:
            return f"{requirements.get('title', '')}. Requires: {skills}".strip()
    return truncate(jd_text, _JD_QUERY_TOKENS)


async def _select_questions(
    user_id: str, interview_type: str, query_vector: list[float], count: int
) -> list[str]:
    """Relevant, diverse, and fresh for this user (see question_selection)."""
    asked = await interviews_repo.asked_question_ids(user_id)
    candidates = await match_question_bank_v2(
        query_vector, interview_type, asked, max(12, count * 4)
    )
    chosen = select_questions(candidates, count)

    if len(chosen) < count and asked:
        # The user has seen most of the bank: allow repeats rather than a
        # shorter interview, preferring whatever they have not seen.
        picked = [c["id"] for c in chosen]
        more = await match_question_bank_v2(query_vector, interview_type, picked, max(12, count * 4))
        chosen += select_questions(more, count - len(chosen))
    return [c["id"] for c in chosen]


async def _no_report(_text: str) -> None:
    return None


async def _validate_start(user_id: str, resume_id: str) -> dict:
    """Everything that can be refused immediately (wrong resume, no key) is
    refused before any row is created or any job started."""
    resume = await _get_owned_processed_resume(user_id, resume_id)
    gemini_key = await get_key_row(user_id, "gemini", "primary")
    if not gemini_key:
        raise AppError(status.HTTP_412_PRECONDITION_FAILED, "key_missing", "A valid primary Gemini key is required to start an interview")
    return resume


async def _run_setup(
    user_id: str,
    interview_id: str,
    interview_type: str,
    provider: str,
    resume_id: str,
    resume: dict,
    jd_text: str,
    report,
) -> None:
    """The slow part of starting an interview: pick questions, write the brief
    and the opening message, then open the interview. `report` is told which
    step is running (the page shows it while polling the job)."""
    config = get_config(interview_type)
    resume_context = resume.get("digest")

    await report("Reading your resume and the job description...")
    # Embedding is only needed to pick questions or, with no digest yet, to
    # find the resume's most relevant chunks. A behavioral interview with a
    # digest on file spends no embedding request at all.
    selected_question_ids: list[str] = []
    query_vector: list[float] | None = None
    if config.question_count > 0 or not resume_context:
        query = _jd_query(user_id, jd_text)
        query_vector = (await gateway.embed(user_id, [query], kind="query"))[0]

    if config.question_count > 0:
        await report("Choosing questions for you...")
        selected_question_ids = await _select_questions(
            user_id, interview_type, query_vector, config.question_count
        )

    if not resume_context:
        rows = await match_resume_chunks_multi(resume_id, [query_vector], [""], per_query=3)
        resume_context = truncate(
            "\n\n".join(r["content"] for r in rows) or (resume["parsed_text"] or ""),
            _RESUME_FALLBACK_TOKENS,
        )

    await report("Preparing your interviewer...")
    boundary = new_boundary()
    setup_prompt = SETUP_PROMPT.format(
        type_line=config.system_prompt,
        notice=NOTICE,
        goal=goal_for(config.phases[0][0]),
        resume=wrap("resume_digest", resume_context, boundary),
        jd=wrap("job_description", truncate(jd_text, _JD_SETUP_TOKENS), boundary),
    )
    try:
        setup = await gateway.complete_structured(
            user_id,
            provider,
            [Message(role=MessageRole.USER, content=setup_prompt)],
            SetupOut,
            _SETUP_OPTIONS,
        )
        opening_message, brief = setup.opening, setup.brief
    except gateway.StructuredOutputError as err:
        # The model never produced usable JSON, even after a repair try:
        # use whatever greeting can be salvaged and build the brief
        # without another call.
        opening_message = _salvage_opening(err.raw)
        brief = ""
    if not brief:
        brief = truncate(
            f"{truncate(jd_text, 150)}\nCandidate: {resume_context}", _BRIEF_MAX_TOKENS
        )
    # The brief is distilled from untrusted text and will be re-used in
    # every later turn: sanitize it before it is stored.
    brief = sanitize_derived(brief, _BRIEF_MAX_TOKENS)
    opening_message = clean_reply(opening_message) or _FALLBACK_OPENING

    now = datetime.now(UTC)
    ends_at = now + timedelta(minutes=config.total_minutes)

    await _update_interview(
        interview_id,
        {
            "status": "in_progress",
            "phase": config.phases[0][0],
            "started_at": now.isoformat(),
            "ends_at": ends_at.isoformat(),
            "selected_question_ids": selected_question_ids,
            "brief": brief,
        },
    )
    await _append_transcript(interview_id, 0, "ai", opening_message)


async def start_interview(
    user_id: str, interview_type: str, provider: str, resume_id: str, jd_text: str
) -> dict:
    """Runs the whole setup inline and returns the interview (used directly by
    tests; the API goes through begin_setup so the page can poll)."""
    resume = await _validate_start(user_id, resume_id)
    interview_id = await _create_interview_row(user_id, interview_type, jd_text, resume_id, provider)
    try:
        await _run_setup(
            user_id, interview_id, interview_type, provider, resume_id, resume, jd_text, _no_report
        )
    except Exception:
        await _update_interview(interview_id, {"status": "aborted"})
        raise
    return await _get_owned_interview(user_id, interview_id)


SETUP_JOB = "interview_setup"


async def begin_setup(
    user_id: str, interview_type: str, provider: str, resume_id: str, jd_text: str
) -> dict:
    """Validates, creates the interview row and starts the setup as a job.
    Returns {"job_id", "interview_id"} at once; the page polls GET /jobs/{id}.
    If a setup is already running for this user (a double-click) that one is
    returned instead of starting a second."""
    existing = await jobs_repo.active_job(user_id, SETUP_JOB)
    if existing is not None and job_runner.is_stale(existing):
        # Nobody has touched it for minutes: its process is gone. Free the slot.
        await job_runner.fail_stale(existing, "The previous setup stopped responding -- please try again.")
        if existing.get("subject_id"):
            await _update_interview(existing["subject_id"], {"status": "aborted"})
        existing = None
    if existing is not None:
        return {"job_id": existing["id"], "interview_id": existing["subject_id"]}

    resume = await _validate_start(user_id, resume_id)
    interview_id = await _create_interview_row(user_id, interview_type, jd_text, resume_id, provider)

    async def work(report) -> dict:
        await _run_setup(
            user_id, interview_id, interview_type, provider, resume_id, resume, jd_text, report
        )
        return {"interview_id": interview_id}

    async def on_failure() -> None:
        await _update_interview(interview_id, {"status": "aborted"})

    try:
        job, created = await job_runner.launch(user_id, SETUP_JOB, interview_id, work, on_failure)
    except Exception:
        await _update_interview(interview_id, {"status": "aborted"})
        raise
    if not created:
        # Lost a race with a simultaneous request: drop the extra row.
        await _update_interview(interview_id, {"status": "aborted"})
    return {"job_id": job["id"], "interview_id": job["subject_id"]}


# One answer at a time per interview (per process, like the limiter and the
# background tasks). A double-click or a retry while the first request is still
# being answered gets a clear 409 instead of paying for a second LLM call and
# racing the first one for the next turn slot. The database write is atomic
# on its own (append_interview_turns); this just avoids the wasted call.
_turns_in_flight: set[str] = set()


async def submit_turn(user_id: str, interview_id: str, content: str) -> dict:
    if interview_id in _turns_in_flight:
        raise AppError(
            status.HTTP_409_CONFLICT,
            "turn_in_progress",
            "Your previous answer is still being processed -- one moment.",
        )
    _turns_in_flight.add(interview_id)
    try:
        return await _submit_turn(user_id, interview_id, content)
    finally:
        _turns_in_flight.discard(interview_id)


async def _submit_turn(user_id: str, interview_id: str, content: str) -> dict:
    interview = await _get_owned_interview(user_id, interview_id)
    if interview["status"] != "in_progress":
        raise AppError(status.HTTP_409_CONFLICT, "interview_not_active", f"Interview is not in progress (status: {interview['status']})")

    config = get_config(interview["type"])
    elapsed = _elapsed_minutes(interview)
    if elapsed > config.total_minutes + _OVERRUN_GRACE_MINUTES:
        # The time box is fixed: close the interview instead of letting it run on.
        await _update_interview(interview_id, {"status": "completed"})
        raise AppError(status.HTTP_409_CONFLICT, "interview_ended", "This interview's time is up and it has been completed.")
    current_phase = phase_for_elapsed(config, elapsed)
    if current_phase != interview["phase"]:
        await _update_interview(interview_id, {"phase": current_phase})
        interview["phase"] = current_phase

    question_block = ""
    review_note = ""
    question_ids = interview.get("selected_question_ids") or []
    # Only while a problem is actually being worked on -- not during the intro
    # (which would reveal it early) or the wrap-up.
    in_problem = bool(
        config.needs_coding_platform
        and question_ids
        and (current_phase.startswith("problem_") or current_phase == "coding")
    )
    # The reads below do not depend on each other: one round of waiting, not three.
    reads = [_recent_turns(interview_id, MAX_RAW_TURNS_IN_CONTEXT - 1)]
    if in_problem:
        index = min(question_index_for(current_phase), len(question_ids) - 1)
        reads += [_get_question_text(question_ids[index]), _get_review_summary(interview_id, question_ids[index])]
    results = await asyncio.gather(*reads)
    recent = results[0]
    if in_problem:
        question_text, submitted = results[1], results[2]
        if question_text:
            question_block = (
                f"\nCurrent question: {truncate(question_text, _QUESTION_TOKEN_CAP)}"
            )
        # After a submission the reviewer's short assessment steers follow-ups;
        # the reference solution itself never enters this prompt.
        if submitted and submitted.get("summary"):
            review_note = (
                f"The candidate submitted {submitted['language']} code. "
                f"Reviewer's assessment: {submitted['summary']}"
            )

    brief = interview.get("brief") or truncate(interview.get("jd_text") or "", _JD_FALLBACK_TOKENS)
    boundary = new_boundary()
    system_text = TURN_SYSTEM.format(
        type_line=config.system_prompt,
        notice=NOTICE,
        phase=current_phase,
        goal=goal_for(current_phase),
        question=question_block,
    )
    messages = [Message(role=MessageRole.SYSTEM, content=system_text)]
    leading = 1

    def as_message(speaker_is_ai: bool, text: str, cap: int) -> Message:
        # Candidate words are untrusted data; the interviewer's own earlier
        # replies are ours.
        text = truncate(text, cap)
        if speaker_is_ai:
            return Message(role=MessageRole.ASSISTANT, content=text)
        return Message(role=MessageRole.USER, content=wrap("candidate_answer", text, boundary))

    # The candidate's new answer goes into the prompt but is only *saved* once
    # the reply succeeded -- otherwise a failed call (429/503) would leave a
    # dangling answer, and the retry would store it twice.
    for turn in recent:
        messages.append(as_message(turn["speaker"] == "ai", turn["text"], _TURN_TOKEN_CAP))
    messages.append(as_message(False, content, _TURN_TOKEN_CAP * 4))

    # Brief + running summary ride along as data in the conversation, and the
    # window is trimmed to leave room for them.
    context = context_block(brief, interview.get("running_summary"), boundary, review_note)
    # The system message (which carries the current question) and the context
    # block come first; the history keeps at least _MIN_HISTORY_TOKENS however
    # large they are, so a long question never pushes out the conversation.
    fixed = estimate_tokens(system_text) + estimate_tokens(context)
    messages = fit_to_budget(
        messages, max(_PROMPT_BUDGET_TOKENS, fixed + _MIN_HISTORY_TOKENS), keep_leading=leading
    )
    messages = attach_context(messages, leading, context)
    messages = ensure_user_first(messages, leading)

    ai_reply = clean_reply(
        await gateway.complete(user_id, interview["provider"], messages, _TURN_OPTIONS)
    )
    if leaks_protected_text(ai_reply, [NOTICE, TURN_RULES_LINE], window=8):
        # The model echoed its own rules back -- most likely because the
        # candidate asked for them. Say nothing of it; log without the content.
        logger.warning("Interviewer reply filtered: it repeated the interview rules")
        ai_reply = SAFE_REDIRECT

    await _append_turns(interview_id, user_id, content, ai_reply)
    # Folding old turns into the running summary is housekeeping: it runs in
    # the background so it adds no latency to this turn, and a failure (quota,
    # outage) just means it is retried after a later turn.
    background.schedule(
        summarizer.maybe_update_summary(interview, user_id, interview["provider"]),
        name=f"summary:{interview_id}",
        key=f"summary:{interview_id}",
    )

    return {
        "message": ai_reply,
        "phase": current_phase,
        "minutes_remaining": minutes_remaining(config, elapsed),
        "is_final_phase": is_final_phase(config, current_phase),
    }


async def complete_interview(user_id: str, interview_id: str) -> dict:
    interview = await _get_owned_interview(user_id, interview_id)
    if interview["status"] == "completed":
        return interview
    if interview["status"] != "in_progress":
        raise AppError(status.HTTP_409_CONFLICT, "interview_not_active", f"Only an interview in progress can be completed (status: {interview['status']})")
    await _update_interview(interview_id, {"status": "completed"})
    interview["status"] = "completed"
    return interview


async def get_interview(user_id: str, interview_id: str) -> dict:
    return await _get_owned_interview(user_id, interview_id)


async def list_interviews(user_id: str, limit: int = 50, offset: int = 0) -> list[dict]:
    return await interviews_repo.list_interviews(user_id, limit, offset)


async def get_transcript(user_id: str, interview_id: str) -> list[dict]:
    await _get_owned_interview(user_id, interview_id)
    return await interviews_repo.transcript(interview_id)
