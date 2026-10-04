import { redirect } from "next/navigation";
import { GuardQueryError } from "@/lib/auth/guards";
import { createClient } from "@/lib/supabase/server";
import { AccountSetupForm } from "./AccountSetupForm";

export const metadata = { title: "Set up your account" };

export default async function AccountSetupPage() {
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

  // A failed query is not "no profile": show the error boundary (retry) instead of misrouting.
  if (profileError) throw new GuardQueryError("profile");

  // Account setup is a one-time step -- once a profiles row exists, this
  // page has nothing left to do.
  if (profile) {
    redirect("/dashboard");
  }

  const email = user.email ?? "";
  const fullName =
    (user.user_metadata?.full_name as string | undefined) ??
    (user.user_metadata?.name as string | undefined) ??
    "";

  return <AccountSetupForm email={email} fullName={fullName} />;
}
