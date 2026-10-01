/**
 * TEMPORARY DEV/DEMO SCAFFOLDING -- DO NOT SHIP.
 *
 * Section 7 of docs/IMPLEMENTATION.md locks the final auth model as
 * Google-only sign-up. This email/password sign-up view exists purely so
 * the team can create accounts and demo the product before Google OAuth
 * credentials are configured. Delete this whole route (and the "Create a
 * demo account" link on the sign-in page) once Google sign-in is live and
 * verified end-to-end.
 */
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { createClient } from "@/lib/supabase/client";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ThemeToggle } from "@/components/ui/ThemeToggle";

const PASSWORD_MIN_LENGTH = 8;

function validatePassword(password: string): string | null {
  if (password.length < PASSWORD_MIN_LENGTH) {
    return `Password must be at least ${PASSWORD_MIN_LENGTH} characters.`;
  }
  if (!/[0-9]/.test(password) || !/[^A-Za-z0-9]/.test(password)) {
    return "Password must include at least one number and one symbol.";
  }
  return null;
}

export function DemoSignUpView() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [checkEmail, setCheckEmail] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    const validationError = validatePassword(password);
    if (validationError) {
      setError(validationError);
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);
    const supabase = createClient();

    const { data, error: signUpError } = await supabase.auth.signUp({
      email,
      password,
      options: { data: { full_name: fullName || undefined } },
    });

    if (signUpError) {
      setError(signUpError.message);
      setLoading(false);
      return;
    }

    if (!data.session) {
      // Email confirmation is required on this Supabase project -- the
      // account exists but isn't usable until the link is clicked.
      setCheckEmail(true);
      setLoading(false);
      return;
    }

    // Confirmation disabled -- session is live immediately. Create the
    // profiles row now (same role-assignment trigger as the Google flow)
    // and go straight to onboarding, since a password was already set at
    // signup -- there's no separate "set password" step needed here.
    const { error: profileError } = await supabase
      .from("profiles")
      .insert({ id: data.user!.id, full_name: fullName || null });

    if (profileError) {
      setError(profileError.message);
      setLoading(false);
      return;
    }

    router.push("/onboarding");
    router.refresh();
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
          <div className="mb-2 inline-block rounded-full bg-accent px-2 py-0.5 text-xs font-medium text-accent-foreground">
            Demo only
          </div>
          <h1 className="text-xl font-semibold">Create a demo account</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Temporary, for testing before Google sign-in is configured.
          </p>

          {checkEmail ? (
            <p className="mt-6 text-sm text-muted-foreground">
              Check <span className="font-medium">{email}</span> for a
              confirmation link, then{" "}
              <a href="/sign-in" className="text-primary underline-offset-4 hover:underline">
                sign in
              </a>
              .
            </p>
          ) : (
            <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-3">
              <input
                type="text"
                placeholder="Full name (optional)"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="rounded-lg border border-border bg-transparent px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              />
              <input
                type="email"
                required
                placeholder="you@example.com"
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
              <input
                type="password"
                required
                placeholder="Confirm password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="rounded-lg border border-border bg-transparent px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              />
              {error && <p className="text-sm text-destructive">{error}</p>}
              <Button type="submit" disabled={loading}>
                {loading ? "Creating account…" : "Create account"}
              </Button>
              <a
                href="/sign-in"
                className="text-center text-sm text-muted-foreground underline-offset-4 hover:underline"
              >
                Back to sign in
              </a>
            </form>
          )}
        </Card>
      </motion.div>
    </div>
  );
}
