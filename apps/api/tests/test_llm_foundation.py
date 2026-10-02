import pytest

from app.llm.budget import estimate_messages_tokens, estimate_tokens, fit_to_budget, truncate
from app.llm.models import MODELS, model_for
from app.providers.base import Message, MessageRole


def _msg(role: MessageRole, text: str) -> Message:
    return Message(role=role, content=text)


# --- budget ---


def test_estimate_tokens_is_chars_over_four_rounded_up():
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("abcde") == 2


def test_truncate_leaves_short_text_alone_and_cuts_long_text():
    assert truncate("short text", 50) == "short text"
    long_text = "word " * 1000
    cut = truncate(long_text, 20)
    assert estimate_tokens(cut) <= 21
    assert cut.endswith("[...]")


def test_truncate_prefers_a_word_boundary():
    cut = truncate("alpha beta gamma delta epsilon zeta", 6)  # 24 chars max
    assert not cut.removesuffix(" [...]").endswith("gam")  # not mid-word


def test_fit_to_budget_drops_oldest_but_keeps_system_and_latest():
    messages = [
        _msg(MessageRole.SYSTEM, "sys"),
        _msg(MessageRole.USER, "old " * 200),
        _msg(MessageRole.ASSISTANT, "older reply " * 200),
        _msg(MessageRole.USER, "latest question"),
    ]

    fitted = fit_to_budget(messages, max_tokens=60)

    assert fitted[0].content == "sys"
    assert fitted[-1].content == "latest question"
    assert estimate_messages_tokens(fitted) <= 60
    assert len(fitted) < len(messages)


def test_fit_to_budget_truncates_the_last_message_as_a_last_resort():
    messages = [_msg(MessageRole.SYSTEM, "sys"), _msg(MessageRole.USER, "x " * 2000)]

    fitted = fit_to_budget(messages, max_tokens=100)

    assert estimate_messages_tokens(fitted) <= 100 + 8  # truncation marker slack
    assert fitted[-1].content.endswith("[...]")


def test_fit_to_budget_is_a_noop_when_already_within_budget():
    messages = [_msg(MessageRole.SYSTEM, "sys"), _msg(MessageRole.USER, "hi")]
    assert fit_to_budget(messages, max_tokens=1000) == messages


# --- model registry ---


def test_every_provider_has_every_task():
    tasks = {"chat", "interview", "feedback", "extract", "summarize", "validate"}
    for provider, mapping in MODELS.items():
        assert tasks <= set(mapping), f"{provider} is missing tasks: {tasks - set(mapping)}"


def test_model_for_unknown_provider_or_task_raises():
    with pytest.raises(ValueError):
        model_for("nope", "chat")
    with pytest.raises(ValueError):
        model_for("gemini", "nope")


def test_gemini_never_uses_a_retired_or_slow_model():
    for task, model in MODELS["gemini"].items():
        assert "1.5" not in model, f"{task} uses a retired model"
        assert model == "gemini-flash-lite-latest", f"{task}: lite is the measured low-latency choice"
