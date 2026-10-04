import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";

export type Role = "owner" | "admin" | "user";

/**
 * A failed Supabase query is not the same as "no row": redirecting an existing
 * user to account setup or onboarding because of a transient error would be
 * wrong (and could send them through setup again). Throwing lets the nearest
 * error boundary (app/error.tsx) offer a retry.
 */
export class GuardQueryError extends Error {
  constructor(what: string) {
    super(`Could not load your ${what}. Please try again.`);
    this.name = "GuardQueryError";
  }
}

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

  const { data: profile, error: profileError } = await supabase
    .from("profiles")
    .select("id")
    .eq("id", user.id)
    .maybeSingle();

  if (profileError) throw new GuardQueryError("profile");
  if (!profile) {
    redirect("/account-setup");
  }

  const { data: geminiKey, error: keyError } = await supabase
    .from("provider_keys")
    .select("id")
    .eq("user_id", user.id)
    .eq("provider", "gemini")
    .eq("slot", "primary")
    .eq("is_valid", true)
    .maybeSingle();

  if (keyError) throw new GuardQueryError("API key status");
  if (!geminiKey) {
    redirect("/onboarding");
  }

  const { data: roleRow, error: roleError } = await supabase
    .from("roles")
    .select("role")
    .eq("user_id", user.id)
    .maybeSingle();

  if (roleError) throw new GuardQueryError("role");
  const role = (roleRow?.role ?? "user") as Role;

  let permissions: string[] = [];
  if (role === "admin") {
    const { data: permissionRows, error: permissionError } = await supabase
      .from("admin_permissions")
      .select("permission_key")
      .eq("admin_id", user.id);
    if (permissionError) throw new GuardQueryError("permissions");
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
