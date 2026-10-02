"""Token budgeting without a tokenizer or any API call.

chars/4 is a deliberately rough heuristic (close enough for English prose;
it undercounts code and non-Latin text). It's used to *cap* and to *test*
prompt size, not to bill -- real counts come from provider-reported usage.
"""

from collections.abc import Sequence

from app.providers.base import Message

CHARS_PER_TOKEN = 4
_PER_MESSAGE_OVERHEAD = 4  # role markers etc.


def estimate_tokens(text: str) -> int:
    return -(-len(text) // CHARS_PER_TOKEN) if text else 0


def estimate_messages_tokens(messages: Sequence[Message]) -> int:
    return sum(estimate_tokens(m.content) + _PER_MESSAGE_OVERHEAD for m in messages)


def truncate(text: str, max_tokens: int, marker: str = " [...]") -> str:
    """Cut `text` to roughly max_tokens, preferring a word boundary."""
    limit = max_tokens * CHARS_PER_TOKEN
    if len(text) <= limit:
        return text
    cut = text[: max(0, limit - len(marker))]
    space = cut.rfind(" ")
    if space > limit * 0.6:
        cut = cut[:space]
    return cut.rstrip() + marker


def fit_to_budget(
    messages: Sequence[Message], max_tokens: int, keep_leading: int = 1
) -> list[Message]:
    """Drops the oldest messages after the first `keep_leading` (system
    prompts) until the estimate fits. The final message is always kept --
    it's the one being answered -- and is truncated as a last resort."""
    messages = list(messages)
    leading = messages[:keep_leading]
    rest = messages[keep_leading:]

    while len(rest) > 1 and estimate_messages_tokens(leading + rest) > max_tokens:
        rest.pop(0)

    fitted = leading + rest
    if estimate_messages_tokens(fitted) > max_tokens and rest:
        overflow = estimate_messages_tokens(fitted) - max_tokens
        last = rest[-1]
        allowed = max(1, estimate_tokens(last.content) - overflow)
        rest[-1] = Message(role=last.role, content=truncate(last.content, allowed))
        fitted = leading + rest
    return fitted
