"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { apiClient, ApiError } from "@/lib/api-client/fastapi";
import { Button } from "@/components/ui/Button";
import type { KeySlot, ProviderKey, ProviderName } from "@/types/keys";

export function ProviderKeyForm({
  provider,
  slot,
  existing,
  onSaved,
}: {
  provider: ProviderName;
  slot: KeySlot;
  existing?: ProviderKey;
  onSaved: (key: ProviderKey) => void;
}) {
  const [value, setValue] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [justValidated, setJustValidated] = useState<boolean | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!value.trim()) return;

    setLoading(true);
    setError(null);
    setJustValidated(null);

    try {
      const saved = await apiClient.post<ProviderKey>("/keys", {
        provider,
        slot,
        api_key: value.trim(),
      });
      setJustValidated(saved.is_valid);
      setValue("");
      onSaved(saved);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <input
          type="password"
          placeholder={
            existing
              ? existing.is_valid
                ? "Key saved — paste a new one to replace it"
                : "Paste your key"
              : "Paste your key"
          }
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className="flex-1 rounded-lg border border-border bg-transparent px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
        />
        <Button type="submit" variant="secondary" disabled={loading || !value.trim()}>
          {loading ? "Checking…" : "Save"}
        </Button>
      </div>

      <AnimatePresence mode="wait">
        {error && (
          <motion.p
            key="error"
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="text-sm text-destructive"
          >
            {error}
          </motion.p>
        )}
        {justValidated !== null && !error && (
          <motion.p
            key="result"
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className={`text-sm ${justValidated ? "text-green-600 dark:text-green-400" : "text-destructive"}`}
          >
            {justValidated
              ? "Key validated successfully."
              : "Key saved, but it failed validation — double-check it's correct."}
          </motion.p>
        )}
        {existing?.is_valid && justValidated === null && (
          <motion.p
            key="existing"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-sm text-green-600 dark:text-green-400"
          >
            Valid key on file
            {existing.last_validated_at
              ? ` — last checked ${new Date(existing.last_validated_at).toLocaleString()}`
              : ""}
            .
          </motion.p>
        )}
      </AnimatePresence>
    </form>
  );
}
