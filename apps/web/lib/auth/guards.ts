import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";

export type Role = "owner" | "admin" | "user";

/**
 * Ensures the viewer is signed in and has completed account setup
 * (Section 7.3 of the plan: a `profiles` row is the source of truth for
 * "has completed account setup"). Redirects to sign-in or account-setup
 * as appropriate. Returns the authenticated user + their role otherwise.
 */
export async function requireUser() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/sign-in");
  }

  const { data: profile } = await supabase
    .from("profiles")
    .select("id")
    .eq("id", user.id)
    .maybeSingle();

  if (!profile) {
    redirect("/account-setup");
  }

  const { data: geminiKey } = await supabase
    .from("provider_keys")
    .select("id")
    .eq("user_id", user.id)
    .eq("provider", "gemini")
    .eq("slot", "primary")
    .eq("is_valid", true)
    .maybeSingle();

  if (!geminiKey) {
    redirect("/onboarding");
  }

  const { data: roleRow } = await supabase
    .from("roles")
    .select("role")
    .eq("user_id", user.id)
    .maybeSingle();

  const role = (roleRow?.role ?? "user") as Role;

  let permissions: string[] = [];
  if (role === "admin") {
    const { data: permissionRows } = await supabase
      .from("admin_permissions")
      .select("permission_key")
      .eq("admin_id", user.id);
    permissions = (permissionRows ?? []).map((p) => p.permission_key);
  }

  return { user, role, permissions };
}

export async function requireRole(role: Role) {
  const { user, role: currentRole } = await requireUser();
  if (currentRole !== role) {
    redirect("/");
  }
  return { user, role: currentRole };
}

/**
 * Page-level permission guard. Owners always pass; admins need the named
 * permission. Call it at the top of the page itself -- layouts are not
 * re-run on client-side navigation, so a layout check alone is not a guard.
 */
export async function requirePermission(permission: string) {
  const { user, role, permissions } = await requireUser();
  if (role !== "owner" && !(role === "admin" && permissions.includes(permission))) {
    redirect("/");
  }
  return { user, role };
}
