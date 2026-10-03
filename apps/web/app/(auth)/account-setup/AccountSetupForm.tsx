"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Alert } from "@/components/ui/Alert";
import { AuthShell } from "@/components/ui/AuthShell";

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

export function AccountSetupForm({
  email,
  fullName,
}: {
  email: string;
  fullName: string;
}) {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

    // 1. Attach a password credential to this Google-created account, so it
    //    becomes a valid alternate login method going forward.
    const { error: passwordError } = await supabase.auth.updateUser({
      password,
    });
    if (passwordError) {
      setError(passwordError.message);
      setLoading(false);
      return;
    }

    // 2. Create the profiles row -- this is the actual account-creation
    //    moment. A DB trigger handles assigning the Owner/User role.
    const {
      data: { user },
    } = await supabase.auth.getUser();

    if (!user) {
      setError("Session expired -- please sign in again.");
      setLoading(false);
      return;
    }

    const { error: profileError } = await supabase
      .from("profiles")
      .insert({ id: user.id, full_name: fullName || null });

    if (profileError) {
      setError(profileError.message);
      setLoading(false);
      return;
    }

    router.push("/onboarding");
    router.refresh();
  }

  return (
    <AuthShell>
        <Card tone="raised" className="w-full p-7 sm:p-8">
          <h1 className="text-2xl font-semibold tracking-[-0.03em]">Welcome to CyntraAI</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Set a password so you can also sign in with email, in addition to
            Google.
          </p>

          <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-3">
            <div>
              <label className="text-xs font-medium text-muted-foreground">Email</label>
              <input
                type="email"
                value={email}
                disabled
                readOnly
                aria-readonly
                className="field mt-1 w-full"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-muted-foreground">
                New password
              </label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="field mt-1 w-full"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-muted-foreground">
                Confirm password
              </label>
              <input
                type="password"
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="field mt-1 w-full"
              />
            </div>

            {error && <Alert role="alert">{error}</Alert>}

            <Button type="submit" loading={loading} className="mt-2">
              {loading ? "Setting up…" : "Continue"}
            </Button>
          </form>
        </Card>
      </AuthShell>
  );
}
