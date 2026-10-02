"""Interview prompt templates. Static text first, dynamic content last."""

PHASE_GOALS = {
    "intro": "Greet briefly, ask for a short self-introduction.",
    "warm_up": "Ease in with a short background question.",
    "problem_1": "Pose problem 1; probe approach before code, then complexity.",
    "problem_2": "Pose problem 2; probe approach before code, then complexity.",
    "coding": "Pose the coding problem; probe approach, then complexity.",
    "system_design": "Pose a system design problem; probe trade-offs and scale.",
    "design_discussion": "Probe requirements, architecture, trade-offs and scale.",
    "behavioral": "Ask STAR-style behavioral questions, one at a time.",
    "questions": "Ask role-relevant questions one at a time; follow up on answers.",
    "concepts": "Test core concepts with focused questions; follow up on depth.",
    "case_study": "Present a case and probe the candidate's reasoning.",
    "case_presentation": "Present the case clearly, then let the candidate ask questions.",
    "discussion": "Probe the candidate's analysis, assumptions and recommendations.",
    "wrap_up": "Wrap up: ask if they have questions, thank them, close.",
}
DEFAULT_GOAL = "Continue the interview naturally."

SETUP_PROMPT = (
    "{type_line}\n"
    "Return JSON: {{\"brief\": <=120 words: role, level, top requirements, candidate "
    "highlights relevant to them>, \"opening\": <2-3 sentence greeting as the interviewer "
    "plus your first question>}}. Opening is spoken text only.\n"
    "Phase goal: {goal}\n\n"
    "Resume digest:\n{resume}\n\nJob description:\n{jd}"
)

TURN_SYSTEM = (
    "{type_line}\n"
    "Reply in <=3 sentences, one question at a time, no preamble or labels.\n"
    "Phase: {phase}. Goal: {goal}\n"
    "Context: {brief}"
    "{question}"
)

SUMMARY_PROMPT = (
    "Update the interview summary in <=80 words: topics covered and candidate "
    "performance. Factual.\n\n"
    "Summary so far: {previous}\n\nNew turns:\n{turns}"
)


def goal_for(phase: str) -> str:
    return PHASE_GOALS.get(phase, DEFAULT_GOAL)


def question_index_for(phase: str) -> int:
    """problem_N -> N-1; any other phase -> 0."""
    if phase.startswith("problem_"):
        try:
            return max(0, int(phase.split("_", 1)[1]) - 1)
        except ValueError:
            return 0
    return 0
