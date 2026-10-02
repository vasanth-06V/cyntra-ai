"""Fire-and-forget work that must not slow down or fail the user's request
(interview summaries, resume digests).

Tasks run on the event loop, so they die with the process. That is fine for
work that is derived and re-derivable: nothing is marked done until it
succeeded, so the next request simply tries again. Anything that must survive
a restart belongs in the planned jobs table, not here.
"""

import asyncio
import logging
from collections.abc import Coroutine

logger = logging.getLogger(__name__)

_tasks: set[asyncio.Task] = set()
_active_keys: set[str] = set()


def schedule(coro: Coroutine, name: str, key: str | None = None) -> bool:
    """Runs `coro` in the background. With `key`, at most one task per key runs
    at a time (a second request while one is running is dropped, and False is
    returned). Failures are logged, never raised. Context (request id) is
    carried over."""
    if key is not None and key in _active_keys:
        coro.close()
        return False

    task = asyncio.get_running_loop().create_task(coro, name=name)
    _tasks.add(task)
    if key is not None:
        _active_keys.add(key)

    def _done(finished: asyncio.Task) -> None:
        _tasks.discard(finished)
        if key is not None:
            _active_keys.discard(key)
        if finished.cancelled():
            return
        error = finished.exception()
        if error is not None:
            logger.warning("Background task %s failed", name, exc_info=error)

    task.add_done_callback(_done)
    return True


async def drain() -> None:
    """Waits for everything scheduled so far (used by tests and at shutdown)."""
    loop = asyncio.get_running_loop()
    # Forget tasks that belonged to a loop that is gone (a restarted worker, a
    # finished test): they can never complete and must not wedge the wait.
    for task in [t for t in _tasks if t.get_loop() is not loop]:
        _tasks.discard(task)
    while _tasks:
        await asyncio.gather(*list(_tasks), return_exceptions=True)
