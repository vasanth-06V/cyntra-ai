import { requireUser } from "@/lib/auth/guards";
import { SecuritySection } from "./SecuritySection";

export const metadata = { title: "Security" };

function providerLabel(provider: string | undefined): string {
  if (!provider) return "Unknown";
  if (provider === "google") return "Google";
  if (provider === "email") return "Email and password";
  return provider.charAt(0).toUpperCase() + provider.slice(1);
}

export default async function SecurityPage() {
  const { user } = await requireUser();
  return (
    <SecuritySection
      provider={providerLabel(user.app_metadata?.provider)}
      lastSignIn={user.last_sign_in_at ?? null}
    />
  );
}
