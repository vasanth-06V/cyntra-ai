import { redirect } from "next/navigation";
import { GuardQueryError } from "@/lib/auth/guards";
import { createClient } from "@/lib/supabase/server";
import { OnboardingFlow } from "./OnboardingFlow";

export const metadata = { title: "Get started" };

export default async function OnboardingPage() {
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

  if (!profile) {
    redirect("/account-setup");
  }

  return <OnboardingFlow />;
}
