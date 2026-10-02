import pytest

from app.core import db as core_db

from app.core import background
from app.core.throttle import throttle
from app.llm.keystate import cooldowns


@pytest.fixture(autouse=True)
def _tests_never_reach_supabase(monkeypatch):
    """Safety net: a unit test that forgets to fake the database fails loudly
    instead of silently talking to the real project. (The integration fixtures
    install their own in-memory fake over this.)"""

    def refuse(*args, **kwargs):
        raise RuntimeError("A test tried to reach the real Supabase -- fake the db layer instead.")

    core_db.get_supabase.cache_clear()
    monkeypatch.setattr(core_db, "create_client", refuse)
    yield
    core_db.get_supabase.cache_clear()


@pytest.fixture(autouse=True)
def _reset_process_wide_state():
    """Throttles and key cooldowns are process-wide; keep tests independent."""
    throttle.reset()
    cooldowns.clear()
    background._tasks.clear()
    background._active_keys.clear()
    yield
    throttle.reset()
    cooldowns.clear()
    background._tasks.clear()
    background._active_keys.clear()
