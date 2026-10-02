"""Token budgeting without a tokenizer or any API call.

chars/4 is a deliberately rough heuristic (close enough for English prose;
it undercounts code and non-Latin text). It's used to *cap* and to *test*
prompt size, not to bill -- real counts come from provider-reported usage.
"""

import re
from collections.abc import Sequence

from app.providers.base import Message, MessageRole

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


def ensure_user_first(
    messages: Sequence[Message], keep_leading: int = 0, placeholder: str | None = None
) -> list[Message]:
    """Providers want the first non-system message to come from the user
    (Claude rejects anything else; Gemini is strict about turn order). A
    sliding window can start on an assistant turn, so either drop that turn
    or, with a placeholder, put a short user line in front of it."""
    leading = list(messages[:keep_leading])
    body = list(messages[keep_leading:])
    if body and body[0].role == MessageRole.ASSISTANT:
        if placeholder:
            body.insert(0, Message(role=MessageRole.USER, content=placeholder))
        elif len(body) > 1:
            body = body[1:]
    return leading + body


_SENTENCE_END = re.compile(r"[.!?][\"')\]]*(?=\s|$)")


def trim_to_sentence(text: str, min_keep: float = 0.4) -> str:
    """For a reply cut off by the output cap: drop the dangling fragment so
    the user sees complete sentences. If there is no sentence end in the
    latter 60% of the text, keep it all and mark the cut with an ellipsis."""
    text = text.rstrip()
    ends = [m.end() for m in _SENTENCE_END.finditer(text)]
    if ends and ends[-1] == len(text):
        return text  # already ends on a sentence boundary
    if ends and ends[-1] >= len(text) * min_keep:
        return text[: ends[-1]].rstrip()
    return text + " [...]"
