"use client";

import { useEffect, useState } from "react";
import { apiClient, ApiError } from "@/lib/api-client/fastapi";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { RefreshIcon } from "@/components/ui/icons";
import { PageHeader } from "@/components/ui/PageHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import { UsageToday } from "@/components/settings/UsageToday";
import { ProviderKeySection } from "@/components/settings/ProviderKeySection";
import type { ProviderKey } from "@/types/keys";

export function ApiKeysView() {
  const [keys, setKeys] = useState<ProviderKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    apiClient
      .get<ProviderKey[]>("/keys")
      .then((k) => {
        setKeys(k);
        setError(null);
      })
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Could not load keys.")
      )
      .finally(() => setLoading(false));
  }, [attempt]);

  return (
    <div className="max-w-3xl">
      <PageHeader
        title="API Keys"
        description="Manage the BYOK provider keys used across CyntraAI."
      />

      {loading ? (
        <div role="status" className="mt-6 flex flex-col gap-4">
          <span className="sr-only">Loading…</span>
          <Skeleton className="h-52 w-full rounded-xl" />
          <Skeleton className="h-44 w-full rounded-xl" />
        </div>
      ) : error ? (
        <div className="mt-6 flex flex-col items-start gap-3">
          <Alert role="alert" className="w-full">
            {error}
          </Alert>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setLoading(true);
              setAttempt((n) => n + 1);
            }}
          >
            <RefreshIcon size={14} />
            Try again
          </Button>
        </div>
      ) : (
        <div className="stagger mt-6 flex flex-col gap-4">
          <ProviderKeySection
            provider="gemini"
            keys={keys}
            onKeysChange={setKeys}
            required
          />
          <ProviderKeySection provider="groq" keys={keys} onKeysChange={setKeys} />
          <ProviderKeySection provider="claude" keys={keys} onKeysChange={setKeys} />
          <UsageToday />
        </div>
      )}
    </div>
  );
}
