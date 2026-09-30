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

  const { data: roleRow } = await supabase
    .from("roles")
    .select("role")
    .eq("user_id", user.id)
    .maybeSingle();

  return { user, role: (roleRow?.role ?? "user") as Role };
}

export async function requireRole(role: Role) {
  const { user, role: currentRole } = await requireUser();
  if (currentRole !== role) {
    redirect("/");
  }
  return { user, role: currentRole };
}
