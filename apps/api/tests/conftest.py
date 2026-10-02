import pytest

from app.core.throttle import throttle


@pytest.fixture(autouse=True)
def _reset_throttle():
    """Throttle state is process-wide; keep tests independent of each other."""
    throttle.reset()
    yield
    throttle.reset()
