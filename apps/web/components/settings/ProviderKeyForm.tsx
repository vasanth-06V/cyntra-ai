"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { apiClient, ApiError } from "@/lib/api-client/fastapi";
import { Button } from "@/components/ui/Button";
import { AlertIcon, CheckIcon } from "@/components/ui/icons";
import type { KeySlot, ProviderKey, ProviderName } from "@/types/keys";

export function ProviderKeyForm({
  provider,
  slot,
  existing,
  onSaved,
  onDeleted,
}: {
  provider: ProviderName;
  slot: KeySlot;
  existing?: ProviderKey;
  onSaved: (key: ProviderKey) => void;
  onDeleted?: (key: ProviderKey) => void;
}) {
  const [value, setValue] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [justValidated, setJustValidated] = useState<boolean | null>(null);
  const [removing, setRemoving] = useState(false);

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

  async function handleDelete() {
    if (!existing || !onDeleted) return;
    if (!window.confirm(`Delete your saved ${provider} ${slot} key? You can add it again later.`)) return;
    setRemoving(true);
    setError(null);
    try {
      await apiClient.delete(`/keys/${existing.id}`);
      setJustValidated(null);
      onDeleted(existing);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not delete the key.");
    } finally {
      setRemoving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2 sm:flex-nowrap">
        <input
          type="password"
          aria-label={`${provider} ${slot} API key`}
          autoComplete="off"
          placeholder={
            existing
              ? existing.is_valid
                ? "Key saved — paste a new one to replace it"
                : "Paste your key"
              : "Paste your key"
          }
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className="field min-w-0 flex-1"
        />
        <Button type="submit" variant="primary" loading={loading} disabled={!value.trim()}>
          {loading ? "Checking…" : "Save"}
        </Button>
        {existing && onDeleted && (
          <Button type="button" variant="danger" onClick={handleDelete} loading={removing} disabled={loading}>
            {removing ? "Deleting…" : "Delete"}
          </Button>
        )}
      </div>

      <AnimatePresence mode="wait">
        {error && (
          <motion.p
            key="error"
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="flex items-center gap-1.5 text-sm text-destructive"
          >
            <AlertIcon size={14} className="shrink-0" />
            {error}
          </motion.p>
        )}
        {justValidated !== null && !error && (
          <motion.p
            key="result"
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className={`flex items-center gap-1.5 text-sm ${justValidated ? "text-success" : "text-destructive"}`}
          >
            {justValidated ? <CheckIcon size={14} className="shrink-0" /> : <AlertIcon size={14} className="shrink-0" />}
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
            className="flex items-center gap-1.5 text-sm text-success"
          >
            <CheckIcon size={14} className="shrink-0" />
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
