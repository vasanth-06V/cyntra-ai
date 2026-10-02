"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { createClient } from "@/lib/supabase/client";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ThemeToggle } from "@/components/ui/ThemeToggle";

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
    <div className="flex min-h-screen flex-col items-center justify-center gap-8 p-6">
      <div className="absolute right-6 top-6">
        <ThemeToggle />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: "easeOut" }}
      >
        <Card className="w-full max-w-sm p-8">
          <h1 className="text-xl font-semibold">CyntraAI</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Sign in to continue.
          </p>

          {!emailMode ? (
            <>
              <Button
                onClick={signInWithGoogle}
                disabled={loading}
                className="mt-6 w-full"
              >
                {loading ? "Redirecting…" : "Continue with Google"}
              </Button>

              {error && (
                <p role="alert" className="mt-3 text-sm text-destructive">{error}</p>
              )}

              <button
                type="button"
                onClick={() => setEmailMode(true)}
                className="mt-4 w-full text-center text-sm text-muted-foreground underline-offset-4 hover:underline cursor-pointer"
              >
                Sign in with email &amp; password instead
              </button>

              {/* TEMPORARY DEV/DEMO LINK -- remove alongside app/(auth)/sign-up
                  once Google sign-in is configured and verified end-to-end. */}
              <a
                href="/sign-up"
                className="mt-2 block text-center text-xs text-muted-foreground underline-offset-4 hover:underline"
              >
                Create a demo account (dev only)
              </a>
            </>
          ) : (
            <EmailPasswordSignIn onBack={() => setEmailMode(false)} />
          )}
        </Card>
      </motion.div>
    </div>
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
        placeholder="you@gmail.com"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        className="rounded-lg border border-border bg-transparent px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
      />
      <input
        type="password"
        required
        placeholder="Password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        className="rounded-lg border border-border bg-transparent px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
      />
      {error && <p className="text-sm text-destructive">{error}</p>}
      <Button type="submit" disabled={loading}>
        {loading ? "Signing in…" : "Sign in"}
      </Button>
      <button
        type="button"
        onClick={onBack}
        className="text-center text-sm text-muted-foreground underline-offset-4 hover:underline cursor-pointer"
      >
        Back to Google sign-in
      </button>
    </form>
  );
}
