from app.core.db import get_supabase
from app.db.base import run


async def database_reachable() -> None:
    """Raises if one cheap read against the database fails."""
    supabase = get_supabase()

    def _q():
        return supabase.table("profiles").select("id").limit(1).execute()

    await run(_q)
