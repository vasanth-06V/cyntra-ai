"""The coding round: one submission per problem, reviewed by logic against the
question bank's reference solution in ONE structured LLM call that also
produces the interviewer's reaction. See docs/PHASE7_PLAN.md."""

import logging

from fastapi import status

from app.coding.schemas import ReviewOut
from app.core import jobs as job_runner
from app.core.errors import AppError
from app.db import interviews as interviews_repo
from app.db import jobs as jobs_repo
from app.db import questions as questions_repo
from app.db import submissions as submissions_repo
from app.interviews.orchestrator import phase_for_elapsed
from app.interviews.service import _OVERRUN_GRACE_MINUTES, _elapsed_minutes
from app.interviews.types import get_config
from app.llm import gateway
from app.llm.budget import truncate
from app.llm.options import LLMOptions
from app.llm.prompts.coding import NO_REFERENCE, REVIEW_SYSTEM
from app.llm.prompts.interview import goal_for, question_index_for
from app.llm.untrusted import (
    NOTICE,
    clean_reply,
    leaks_protected_text,
    neutralize_tags,
    new_boundary,
    sanitize_derived,
    strip_controls,
    wrap,
)
from app.providers.base import Message, MessageRole

logger = logging.getLogger(__name__)

REVIEW_JOB = "code_review"
MAX_CODE_CHARS = 8000

_REVIEW_OPTIONS = LLMOptions(
    task="judge",
    max_output_tokens=700,
    temperature=0.2,
    feature="code_review",
    prompt_id="coding.review",
    prompt_version="1",
)

_QUESTION_TOKENS = 400
_REFERENCE_TOKENS = 2000
_CODE_TOKENS = 2200
_TURN_TOKENS = 100
_RECENT_TURNS = 4
_BRIEF_TOKENS = 200

FALLBACK_MESSAGE = (
    "Thanks for submitting. Walk me through your approach and why you chose it, "
    "and tell me what you would check first for edge cases."
)


def clean_language(language: str) -> str:
    """A free-form label ("C++", "Python 3", "Rust"): printable, one line, short."""
    label = neutralize_tags(strip_controls(language)).replace("\n", " ").strip()
    return label[:30]


def _problem_phase(interview: dict) -> tuple[str, int, str]:
    """(phase, index, question_id) of the problem being worked on, or a
    409 explaining why a submission isn't possible now."""
    if interview["status"] != "in_progress":
        raise AppError(
            status.HTTP_409_CONFLICT,
            "interview_not_active",
            f"Interview is not in progress (status: {interview['status']})",
        )
    config = get_config(interview["type"])
    if not config.needs_coding_platform:
        raise AppError(status.HTTP_409_CONFLICT, "no_coding_round", "This interview has no coding round.")
    elapsed = _elapsed_minutes(interview)
    if elapsed > config.total_minutes + _OVERRUN_GRACE_MINUTES:
        raise AppError(status.HTTP_409_CONFLICT, "interview_ended", "This interview's time is up.")
    phase = phase_for_elapsed(config, elapsed)
    ids = interview.get("selected_question_ids") or []
    if not (phase.startswith("problem_") or phase == "coding") or not ids:
        raise AppError(
            status.HTTP_409_CONFLICT,
            "not_a_coding_phase",
            "There is no coding problem to submit for right now.",
        )
    index = min(question_index_for(phase), len(ids) - 1)
    return phase, index, ids[index]


async def get_problem(user_id: str, interview_id: str) -> dict:
    """What the page needs to show the editor: whether it is active, which
    problem, and whether it was already submitted. The problem text is what
    the interviewer states anyway; the reference solution never appears."""
    interview = await interviews_repo.get_owned_interview(user_id, interview_id)
    config = get_config(interview["type"])
    base = {"enabled": False, "active": False, "phase": interview.get("phase")}
    if not config.needs_coding_platform or interview["status"] != "in_progress":
        return base
    try:
        phase, index, question_id = _problem_phase(interview)
    except AppError:
        return {**base, "enabled": True}

    ids = interview.get("selected_question_ids") or []
    submission = await submissions_repo.get_for_question(interview_id, question_id)
    job = await jobs_repo.active_job(user_id, REVIEW_JOB)
    return {
        "enabled": True,
        "active": True,
        "phase": phase,
        "problem_number": index + 1,
        "total_problems": len(ids),
        "question": await interviews_repo.question_text(question_id),
        "submission": (
            {
                "language": submission["language"],
                "line_count": submission["line_count"],
                "status": submission["status"],
            }
            if submission
            else None
        ),
        "review_job_id": job["id"] if job and submission and submission["status"] == "review" else None,
    }


def _review_messages(
    interview: dict,
    config,
    phase: str,
    question: str,
    reference: str | None,
    reference_language: str | None,
    language: str,
    code: str,
    recent: list[dict],
) -> list[Message]:
    boundary = new_boundary()
    system = REVIEW_SYSTEM.format(
        type_line=config.system_prompt, notice=NOTICE, goal=goal_for(phase)
    )
    if reference:
        ref_block = wrap(
            "reference_solution",
            f"[{reference_language or 'unspecified language'}]\n{truncate(reference, _REFERENCE_TOKENS)}",
            boundary,
        )
    else:
        ref_block = NO_REFERENCE
    transcript = "\n".join(
        f"{'Interviewer' if t['speaker'] == 'ai' else 'Candidate'}: {truncate(t['text'], _TURN_TOKENS)}"
        for t in recent
    )
    parts = [
        wrap("problem", truncate(question, _QUESTION_TOKENS), boundary),
        ref_block,
        wrap(
            "candidate_code",
            f"[{language}, {len(code.splitlines())} lines]\n{truncate(code, _CODE_TOKENS)}",
            boundary,
        ),
    ]
    if interview.get("brief"):
        parts.append(wrap("interview_brief", truncate(interview["brief"], _BRIEF_TOKENS), boundary))
    if transcript:
        parts.append(wrap("recent_conversation", transcript, boundary))
    return [
        Message(role=MessageRole.SYSTEM, content=system),
        Message(role=MessageRole.USER, content="\n\n".join(parts)),
    ]


def _stored_verdict(review: ReviewOut) -> tuple[dict, str]:
    """What is kept: model output derived from untrusted code, so every text
    field is sanitized before it is stored and re-used in later prompts."""
    verdict = {
        "trace": sanitize_derived(review.trace, 300),
        "approach": review.approach,
        "result": review.result,
        "issues": [sanitize_derived(i, 60) for i in review.issues],
        "edge_cases_missed": [sanitize_derived(i, 60) for i in review.edge_cases_missed],
        "candidate_complexity": sanitize_derived(review.candidate_complexity, 30),
        "reference_complexity": sanitize_derived(review.reference_complexity, 30),
        "confidence": review.confidence,
    }
    return verdict, sanitize_derived(review.summary, 100)


async def begin_review(
    user_id: str, interview_id: str, language: str, code: str
) -> dict:
    """Validates, claims the single submission and starts the review as a job.
    Returns {"job_id", "submission_id"} at once; the page polls /jobs/{id}."""
    interview = await interviews_repo.get_owned_interview(user_id, interview_id)
    phase, _index, question_id = _problem_phase(interview)

    language = clean_language(language)
    if not language:
        raise AppError(status.HTTP_422_UNPROCESSABLE_ENTITY, "validation_failed", "Please name the language.")
    code = strip_controls(code)
    if not code.strip():
        raise AppError(status.HTTP_422_UNPROCESSABLE_ENTITY, "validation_failed", "Write some code before submitting.")
    if len(code) > MAX_CODE_CHARS:
        raise AppError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "code_too_long",
            f"That solution is too long to review (max {MAX_CODE_CHARS} characters).",
        )

    submission = await submissions_repo.create_submission(
        interview_id, user_id, question_id, language, code
    )
    if submission is None:
        raise AppError(
            status.HTTP_409_CONFLICT,
            "already_submitted",
            "You have already submitted a solution for this problem.",
        )
    submission_id = submission["id"]
    config = get_config(interview["type"])

    async def work(report) -> dict:
        await report("Reading your code...")
        material = await questions_repo.get_review_material(question_id)
        if not material:
            raise AppError(status.HTTP_404_NOT_FOUND, "not_found", "The problem could not be found.")
        recent = await interviews_repo.recent_turns(interview_id, _RECENT_TURNS)

        await report("Comparing with the reference solution...")
        messages = _review_messages(
            interview,
            config,
            phase,
            material["question"],
            material.get("solution_code"),
            material.get("solution_language"),
            language,
            code,
            recent,
        )
        try:
            review = await gateway.complete_structured(
                user_id, interview["provider"], messages, ReviewOut, _REVIEW_OPTIONS
            )
        except gateway.StructuredOutputError as exc:
            logger.warning("Code review produced no usable verdict: %s", exc)
            raise AppError(
                status.HTTP_502_BAD_GATEWAY,
                "review_failed",
                "Couldn't review your solution this time -- your submit was not used, please try again.",
            ) from exc

        await report("Preparing feedback...")
        message = clean_reply(review.interviewer_message)
        protected = [NOTICE] + ([material["solution_code"]] if material.get("solution_code") else [])
        if not message or leaks_protected_text(message, protected, window=8):
            if message:
                logger.warning("Reviewer message filtered: it repeated protected text")
            message = FALLBACK_MESSAGE

        verdict, summary = _stored_verdict(review)
        await submissions_repo.mark_done(submission_id, verdict, summary)
        marker = f"[Submitted a solution in {language} · {len(code.splitlines())} lines]"
        await interviews_repo.append_turns(interview_id, user_id, marker, message)
        return {"submission_id": submission_id, "message": message}

    async def on_failure() -> None:
        # The candidate's single submit is only used up by a finished review.
        await submissions_repo.mark_failed(submission_id)

    try:
        job, created = await job_runner.launch(user_id, REVIEW_JOB, submission_id, work, on_failure)
    except Exception:
        await submissions_repo.mark_failed(submission_id)
        raise
    if not created:
        await submissions_repo.mark_failed(submission_id)
        raise AppError(
            status.HTTP_409_CONFLICT,
            "review_in_progress",
            "A review is already in progress -- one moment.",
        )
    return {"job_id": job["id"], "submission_id": submission_id}
