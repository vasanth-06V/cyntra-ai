import logging

from app.db import usage as usage_repo
from app.llm.options import Usage

logger = logging.getLogger(__name__)


async def record(
    user_id: str,
    provider: str,
    kind: str,
    usage: Usage,
    est_input_tokens: int = 0,
    est_output_tokens: int = 0,
) -> None:
    """Adds this call to the user's daily totals. Provider-reported token
    counts win; where a provider didn't report any (e.g. Groq streaming) the
    caller's estimate is used instead, so the *request* count -- the number
    quotas are actually enforced on -- is always right.

    Bookkeeping must never fail a user's request, so errors are logged and
    swallowed."""
    params = {
        "p_user_id": user_id,
        "p_provider": provider,
        "p_kind": kind,
        "p_requests": usage.requests or 1,
        "p_input": usage.input_tokens or est_input_tokens,
        "p_output": usage.output_tokens or est_output_tokens,
    }

    try:
        await usage_repo.record_usage(params)
    except Exception:
        logger.warning("Could not record LLM usage", exc_info=True)
