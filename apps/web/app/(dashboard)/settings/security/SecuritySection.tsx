"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { CheckIcon } from "@/components/ui/icons";
import { LocalTime } from "@/components/ui/LocalTime";

const PROTECTIONS = [
  "Your AI provider keys are encrypted before they are stored.",
  "Your resumes and chats are visible only to your account.",
  "Interview reports are deleted automatically after 7 days.",
];

export function SecuritySection({ provider, lastSignIn }: { provider: string; lastSignIn: string | null }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function signOutEverywhere() {
    if (busy) return;
    setBusy(true);
    setError(null);
    const { error: err } = await createClient().auth.signOut({ scope: "global" });
    if (err) {
      setBusy(false);
      setError(err.message || "Could not sign you out of your other devices.");
      return;
    }
    router.push("/sign-in");
    router.refresh();
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Security" description="How you sign in, your sessions, and how your data is protected." />

      <Card className="p-5 sm:p-6">
        <h2 className="text-sm font-semibold">Sign-in</h2>
        <dl className="mt-4 grid gap-4 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-muted-foreground">Sign-in method</dt>
            <dd className="mt-0.5 font-medium">{provider}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Last sign-in</dt>
            <dd className="mt-0.5 font-medium tabular-nums">{lastSignIn ? <LocalTime iso={lastSignIn} /> : "Not available"}</dd>
          </div>
        </dl>
        <p className="mt-4 text-sm leading-6 text-muted-foreground">
          {provider === "Google"
            ? "CyntraAI never sees your Google password. To change it or turn on two-step verification, use your Google account settings."
            : "Manage your password and sign-in options with your sign-in provider."}
        </p>
      </Card>

      <Card className="p-5 sm:p-6">
        <h2 className="text-sm font-semibold">Sessions</h2>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          Signed in somewhere you don&apos;t trust, or lost a device? Sign out everywhere, including this browser, and
          sign back in when you&apos;re ready.
        </p>
        {error && (
          <Alert role="alert" className="mt-3">
            {error}
          </Alert>
        )}
        <Button variant="outline" className="mt-4" loading={busy} onClick={() => void signOutEverywhere()}>
          Sign out of all devices
        </Button>
      </Card>

      <Card className="p-5 sm:p-6">
        <h2 className="text-sm font-semibold">How your data is protected</h2>
        <ul className="mt-3 flex flex-col gap-2.5">
          {PROTECTIONS.map((text) => (
            <li key={text} className="flex items-start gap-2.5 text-sm leading-6">
              <CheckIcon size={16} className="mt-1 shrink-0 text-success" />
              {text}
            </li>
          ))}
        </ul>
        <p className="mt-4 text-sm">
          <Link href="/privacy" className="font-medium text-primary underline-offset-4 hover:underline">
            Read the privacy notice
          </Link>
        </p>
      </Card>
    </div>
  );
}
