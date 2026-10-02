import asyncio
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


async def run(fn: Callable[[], T]) -> T:
    """Runs a blocking supabase-py call off the event loop."""
    return await asyncio.to_thread(fn)
