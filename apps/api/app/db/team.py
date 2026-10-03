from app.core.db import get_supabase
from app.db.base import run

_PAGE = 200


async def list_auth_users() -> list[dict]:
    """Sign-in accounts (id, email). Emails live in Supabase Auth, which only the
    admin API can list; `profiles` is readable by its own owner only."""
    supabase = get_supabase()

    def _q():
        return supabase.auth.admin.list_users(page=1, per_page=_PAGE)

    users = await run(_q)
    return [{"id": str(u.id), "email": getattr(u, "email", None)} for u in users]


async def list_profiles() -> list[dict]:
    supabase = get_supabase()

    def _q():
        return supabase.table("profiles").select("id, full_name, created_at").limit(_PAGE).execute()

    return (await run(_q)).data or []


async def list_roles() -> list[dict]:
    supabase = get_supabase()

    def _q():
        return supabase.table("roles").select("user_id, role").limit(_PAGE).execute()

    return (await run(_q)).data or []


async def list_permissions() -> list[dict]:
    supabase = get_supabase()

    def _q():
        return supabase.table("admin_permissions").select("admin_id, permission_key").limit(1000).execute()

    return (await run(_q)).data or []


async def profile_exists(user_id: str) -> bool:
    supabase = get_supabase()

    def _q():
        return supabase.table("profiles").select("id").eq("id", user_id).limit(1).execute()

    return bool((await run(_q)).data)


async def set_role(user_id: str, role: str) -> None:
    supabase = get_supabase()

    def _q():
        return supabase.table("roles").upsert({"user_id": user_id, "role": role}, on_conflict="user_id").execute()

    await run(_q)


async def replace_permissions(admin_id: str, keys: list[str], granted_by: str) -> None:
    """The admin's permission set becomes exactly `keys`."""
    supabase = get_supabase()

    def _delete():
        return supabase.table("admin_permissions").delete().eq("admin_id", admin_id).execute()

    def _insert():
        rows = [{"admin_id": admin_id, "permission_key": k, "granted_by": granted_by} for k in keys]
        return supabase.table("admin_permissions").insert(rows).execute()

    await run(_delete)
    if keys:
        await run(_insert)
