"use client";

import { useEffect, useState } from "react";
import { apiClient, ApiError } from "@/lib/api-client/fastapi";
import { Alert } from "@/components/ui/Alert";
import { PageHeader } from "@/components/ui/PageHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import { UsageToday } from "@/components/settings/UsageToday";
import { ProviderKeySection } from "@/components/settings/ProviderKeySection";
import type { ProviderKey } from "@/types/keys";

export function ApiKeysView() {
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
        <Alert role="alert" className="mt-6">
          {error}
        </Alert>
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
