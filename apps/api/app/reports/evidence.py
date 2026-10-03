"""The evidence pack for a report: everything that can be worked out without
an LLM -- the trimmed transcript, which phase each answer belonged to, answer
statistics, and the stored code-review facts. Pure functions, unit-tested."""

from dataclasses import dataclass, field
from datetime import datetime

from app.interviews.orchestrator import phase_for_elapsed
from app.interviews.types import InterviewTypeConfig
from app.llm.budget import estimate_tokens, truncate

MARKER_PREFIX = "[Submitted a solution in"
_ANSWER_TOKENS = 150
_QUESTION_TOKENS = 60
_KEEP_OPENING = 4  # turns always kept from the start when the transcript is trimmed


@dataclass
class Evidence:
    transcript: str
    answers: list[str]  # the candidate's real answers (for quote checking), no code markers
    answer_count: int
    avg_words: int
    minutes_used: float
    phases: list[dict] = field(default_factory=list)  # [{"phase", "answers"}]
    omitted_turns: int = 0


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))


def is_answer(turn: dict) -> bool:
    """A candidate turn that is speech, not the marker left by a code submission."""
    return turn["speaker"] == "user" and not turn["text"].startswith(MARKER_PREFIX)


def count_answers(turns: list[dict]) -> int:
    return sum(1 for t in turns if is_answer(t))


def build_evidence(
    interview: dict, config: InterviewTypeConfig, turns: list[dict], budget_tokens: int = 6000
) -> Evidence:
    ordered = sorted(turns, key=lambda t: t["turn_index"])
    started = _parse(interview["started_at"]) if interview.get("started_at") else None

    lines: list[tuple[int, str]] = []  # (tokens, line)
    answers: list[str] = []
    per_phase: dict[str, int] = {}
    last_ts = started
    for turn in ordered:
        ts = _parse(turn["created_at"]) if turn.get("created_at") else None
        if ts and (last_ts is None or ts > last_ts):
            last_ts = ts
        if turn["speaker"] == "ai":
            text = truncate(turn["text"], _QUESTION_TOKENS)
            line = f"Interviewer: {text}"
        elif is_answer(turn):
            text = truncate(turn["text"], _ANSWER_TOKENS)
            answers.append(turn["text"])
            if started and ts:
                phase = phase_for_elapsed(config, max(0.0, (ts - started).total_seconds() / 60))
                per_phase[phase] = per_phase.get(phase, 0) + 1
            line = f"Candidate: {text}"
        else:
            line = f"Candidate: {turn['text']}"  # the short marker for a code submission
            text = turn["text"]
        lines.append((estimate_tokens(line), line))

    omitted = 0
    if sum(t for t, _ in lines) > budget_tokens and len(lines) > _KEEP_OPENING:
        head = lines[:_KEEP_OPENING]
        used = sum(t for t, _ in head)
        tail: list[tuple[int, str]] = []
        for tokens, line in reversed(lines[_KEEP_OPENING:]):
            if used + tokens > budget_tokens:
                break
            tail.append((tokens, line))
            used += tokens
        tail.reverse()
        omitted = len(lines) - len(head) - len(tail)
        lines = head + [(10, f"[... {omitted} turns omitted ...]")] + tail

    words = [len(a.split()) for a in answers]
    minutes = ((last_ts - started).total_seconds() / 60) if (started and last_ts) else 0.0
    return Evidence(
        transcript="\n".join(line for _, line in lines),
        answers=answers,
        answer_count=len(answers),
        avg_words=round(sum(words) / len(words)) if words else 0,
        minutes_used=round(minutes, 1),
        phases=[{"phase": name, "answers": per_phase.get(name, 0)} for name, _ in config.phases],
        omitted_turns=omitted,
    )


def coding_facts(submissions: list[dict], question_ids: list[str]) -> list[dict]:
    """The finished code reviews, in problem order, ready to show and to feed
    the score caps. Taken from the stored verdict -- never re-generated."""
    facts = []
    for sub in submissions:
        if sub.get("status") != "done" or not sub.get("verdict"):
            continue
        verdict = sub["verdict"]
        try:
            number = question_ids.index(sub.get("question_id")) + 1
        except ValueError:
            number = len(facts) + 1
        facts.append(
            {
                "problem": number,
                "language": sub["language"],
                "line_count": sub["line_count"],
                "result": verdict.get("result", "incomplete"),
                "approach": verdict.get("approach", ""),
                "issues": verdict.get("issues", []),
                "edge_cases_missed": verdict.get("edge_cases_missed", []),
                "candidate_complexity": verdict.get("candidate_complexity", ""),
                "reference_complexity": verdict.get("reference_complexity", ""),
            }
        )
    return sorted(facts, key=lambda f: f["problem"])
