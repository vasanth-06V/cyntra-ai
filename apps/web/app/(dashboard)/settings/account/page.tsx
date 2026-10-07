import { requireUser } from "@/lib/auth/guards";
import { createClient } from "@/lib/supabase/server";
import { AccountForm } from "./AccountForm";

export const metadata = { title: "Account" };

export default async function AccountPage() {
  const { user, role } = await requireUser();
  const supabase = await createClient();
  const { data: profile } = await supabase
    .from("profiles")
    .select("full_name, created_at")
    .eq("id", user.id)
    .maybeSingle();

  return (
    <AccountForm
      email={user.email ?? ""}
      initialName={profile?.full_name ?? ""}
      role={role}
      memberSince={profile?.created_at ?? user.created_at ?? null}
    />
  );
}
