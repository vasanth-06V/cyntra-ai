"use client";

import { useEffect, useState } from "react";
import { apiClient, ApiError } from "@/lib/api-client/fastapi";
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
    <div>
      <h1 className="text-2xl font-semibold">API Keys</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Manage the BYOK provider keys used across CyntraAI.
      </p>

      {loading ? (
        <p className="mt-6 text-sm text-muted-foreground">Loading…</p>
      ) : error ? (
        <p className="mt-6 text-sm text-destructive">{error}</p>
      ) : (
        <div className="mt-6 flex flex-col gap-4">
          <ProviderKeySection
            provider="gemini"
            keys={keys}
            onKeysChange={setKeys}
            required
          />
          <ProviderKeySection provider="groq" keys={keys} onKeysChange={setKeys} />
          <ProviderKeySection provider="claude" keys={keys} onKeysChange={setKeys} />
        </div>
      )}
    </div>
  );
}
