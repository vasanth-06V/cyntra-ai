"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiClient, ApiError } from "@/lib/api-client/fastapi";
import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/Alert";
import { AuthShell } from "@/components/ui/AuthShell";
import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { ProviderKeySection } from "@/components/settings/ProviderKeySection";
import type { ProviderKey } from "@/types/keys";

export function OnboardingFlow() {
  const router = useRouter();
  const [step, setStep] = useState<1 | 2>(1);
  const [keys, setKeys] = useState<ProviderKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiClient
      .get<ProviderKey[]>("/keys")
      .then(setKeys)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Could not load keys.")
      )
      .finally(() => setLoading(false));
  }, []);

  const hasValidGemini = keys.some(
    (k) => k.provider === "gemini" && k.slot === "primary" && k.is_valid
  );

  function finish() {
    router.push("/dashboard");
    router.refresh();
  }

  return (
    <AuthShell wide>
      <Card tone="raised" className="p-6 sm:p-7">
        <p className="text-xs font-medium uppercase tracking-[0.08em] text-primary" aria-live="polite">
          Step {step} of 2
        </p>
        <div aria-hidden="true" className="mt-2 flex gap-1.5">
          <span className="h-1 flex-1 rounded-full bg-primary" />
          <span className={`h-1 flex-1 rounded-full transition-colors duration-300 ${step === 2 ? "bg-primary" : "bg-border-strong"}`} />
        </div>
        <h1 className="mt-5 text-2xl font-semibold tracking-[-0.03em]">Set up your AI providers</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          CyntraAI is Bring-Your-Own-Key: you use your own API keys, we never
          see your usage costs.
        </p>

        {loading ? (
          <div role="status" className="mt-6 flex flex-col gap-3">
            <span className="sr-only">Loading…</span>
            <Skeleton className="h-40 w-full rounded-xl" />
          </div>
        ) : error ? (
          <Alert role="alert" className="mt-6">{error}</Alert>
        ) : step === 1 ? (
          <div className="mt-6 flex flex-col gap-4">
            <ProviderKeySection
              provider="gemini"
              keys={keys}
              onKeysChange={setKeys}
              required
            />
            <p className="text-xs text-muted-foreground">
              Gemini is required — it powers embeddings used across the
              platform (Interviewing Agent, ATS Score), regardless of which
              model you chat with.
            </p>
            <Button
              onClick={() => setStep(2)}
              disabled={!hasValidGemini}
              className="self-end"
            >
              Continue
            </Button>
          </div>
        ) : (
          <div className="mt-6 flex flex-col gap-4">
            <ProviderKeySection provider="groq" keys={keys} onKeysChange={setKeys} />
            <ProviderKeySection provider="claude" keys={keys} onKeysChange={setKeys} />
            <p className="text-xs text-muted-foreground">
              Optional — you can add or change these anytime from Settings.
            </p>
            <div className="flex justify-between">
              <button
                type="button"
                onClick={() => setStep(1)}
                className="text-sm font-medium text-muted-foreground underline-offset-4 hover:text-foreground hover:underline cursor-pointer"
              >
                Back
              </button>
              <Button onClick={finish}>Finish setup</Button>
            </div>
          </div>
        )}
      </Card>
    </AuthShell>
  );
}
