"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { apiClient, ApiError } from "@/lib/api-client/fastapi";
import { Button } from "@/components/ui/Button";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
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
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 p-6">
      <div className="absolute right-6 top-6">
        <ThemeToggle />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: "easeOut" }}
        className="w-full max-w-lg"
      >
        <h1 className="text-xl font-semibold">Set up your AI providers</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          CyntraAI is Bring-Your-Own-Key: you use your own API keys, we never
          see your usage costs.
        </p>

        {loading ? (
          <p className="mt-6 text-sm text-muted-foreground">Loading…</p>
        ) : error ? (
          <p className="mt-6 text-sm text-destructive">{error}</p>
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
                className="text-sm text-muted-foreground underline-offset-4 hover:underline cursor-pointer"
              >
                Back
              </button>
              <Button onClick={finish}>Finish setup</Button>
            </div>
          </div>
        )}
      </motion.div>
    </div>
  );
}
