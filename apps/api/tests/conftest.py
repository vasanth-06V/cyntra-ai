import pytest

from app.core.throttle import throttle
from app.llm.keystate import cooldowns


@pytest.fixture(autouse=True)
def _reset_process_wide_state():
    """Throttles and key cooldowns are process-wide; keep tests independent."""
    throttle.reset()
    cooldowns.clear()
    yield
    throttle.reset()
    cooldowns.clear()
