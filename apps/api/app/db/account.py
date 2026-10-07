from app.core.db import get_supabase
from app.db.base import run


async def set_full_name(user_id: str, full_name: str) -> bool:
    """Updates the profile name; False when the profile row doesn't exist."""
    supabase = get_supabase()

    def _q():
        return supabase.table("profiles").update({"full_name": full_name}).eq("id", user_id).execute()

    return bool((await run(_q)).data)


async def delete_auth_user(user_id: str) -> None:
    """Deletes the sign-in account. Every table that holds the user's data
    references it with ON DELETE CASCADE, so their rows go with it."""
    supabase = get_supabase()

    def _q():
        return supabase.auth.admin.delete_user(user_id)

    await run(_q)
