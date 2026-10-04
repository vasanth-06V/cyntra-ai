"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { demoSignUpEnabled } from "@/lib/demo-signup";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Alert } from "@/components/ui/Alert";
import { AuthShell } from "@/components/ui/AuthShell";
import { GoogleIcon } from "@/components/ui/icons";

export function SignInView({ initialError = null }: { initialError?: string | null }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(initialError);
  const [emailMode, setEmailMode] = useState(false);

  async function signInWithGoogle() {
    setLoading(true);
    setError(null);
    const supabase = createClient();
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/auth/callback` },
    });
    if (error) {
      setError(error.message);
      setLoading(false);
    }
  }

  return (
    <AuthShell showcase>
      <Card tone="raised" className="w-full p-7 sm:p-8">
        <h1 className="text-2xl font-semibold tracking-[-0.03em]">Welcome back</h1>
        <p className="mt-1.5 text-sm text-muted-foreground">
          Sign in to continue to CyntraAI.
        </p>

        {!emailMode ? (
          <>
            <Button
              onClick={signInWithGoogle}
              loading={loading}
              size="lg"
              variant="outline"
              className="mt-7 w-full"
            >
              {!loading && <GoogleIcon size={18} />}
              {loading ? "Redirecting…" : "Continue with Google"}
            </Button>

            {error && (
              <Alert role="alert" className="mt-4">
                {error}
              </Alert>
            )}

            <div className="my-6 flex items-center gap-3 text-xs text-muted-foreground" aria-hidden="true">
              <span className="h-px flex-1 bg-border" />
              or
              <span className="h-px flex-1 bg-border" />
            </div>

            <button
              type="button"
              onClick={() => setEmailMode(true)}
              className="w-full cursor-pointer text-center text-sm font-medium text-primary underline-offset-4 hover:underline"
            >
              Sign in with email &amp; password instead
            </button>

            {/* TEMPORARY DEV/DEMO LINK -- remove alongside app/(auth)/sign-up
                once Google sign-in is configured and verified end-to-end. */}
            {demoSignUpEnabled() && (
              <a
                href="/sign-up"
                className="mt-3 block text-center text-xs text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
              >
                Create a demo account (dev only)
              </a>
            )}
          </>
        ) : (
          <EmailPasswordSignIn onBack={() => setEmailMode(false)} />
        )}
      </Card>
    </AuthShell>
  );
}

function EmailPasswordSignIn({ onBack }: { onBack: () => void }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const supabase = createClient();
    const { error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });
    if (error) {
      setError(error.message);
      setLoading(false);
      return;
    }
    router.push("/dashboard");
    router.refresh();
  }

  return (
    <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-3">
      <input
        type="email"
        required
        aria-label="Email"
        autoComplete="email"
        placeholder="you@gmail.com"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        className="field"
      />
      <input
        type="password"
        required
        aria-label="Password"
        autoComplete="current-password"
        placeholder="Password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        className="field"
      />
      {error && <Alert role="alert">{error}</Alert>}
      <Button type="submit" loading={loading}>
        {loading ? "Signing in…" : "Sign in"}
      </Button>
      <button
        type="button"
        onClick={onBack}
        className="text-center text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline cursor-pointer"
      >
        Back to Google sign-in
      </button>
    </form>
  );
}
