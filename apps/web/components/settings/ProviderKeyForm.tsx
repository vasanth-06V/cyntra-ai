"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { apiClient, ApiError } from "@/lib/api-client/fastapi";
import { Button } from "@/components/ui/Button";
import { useConfirm } from "@/components/ui/ConfirmProvider";
import { useToast } from "@/components/ui/Toast";
import { AlertIcon, CheckIcon, TrashIcon } from "@/components/ui/icons";
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
  const confirm = useConfirm();
  const { toast } = useToast();
  const [value, setValue] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [justValidated, setJustValidated] = useState<boolean | null>(null);
  const [removing, setRemoving] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = value.trim();
    if (!trimmed) return;
    if (trimmed.length < 8) {
      setError("That key looks too short. Paste the whole key.");
      return;
    }

    setLoading(true);
    setError(null);
    setJustValidated(null);

    try {
      const saved = await apiClient.post<ProviderKey>("/keys", {
        provider,
        slot,
        api_key: trimmed,
      });
      setJustValidated(saved.is_valid);
      setValue("");
      onSaved(saved);
      if (saved.is_valid) {
        toast({ tone: "success", title: `${provider} ${slot} key saved`, description: "It passed validation." });
      } else {
        toast({
          tone: "error",
          title: `${provider} ${slot} key saved, but it failed validation`,
          description: "Double-check that you pasted the right key.",
        });
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete() {
    if (!existing || !onDeleted) return;
    const keyToRemove = existing;
    const isRequiredGemini = provider === "gemini" && slot === "primary";
    setRemoving(true);
    setError(null);
    const ok = await confirm({
      title: `Delete your ${provider} ${slot} key?`,
      description: isRequiredGemini
        ? "Gemini is required: embeddings for interviews and ATS scoring use it. Without a valid Gemini key you will be asked to set it up again. You can add the key again at any time."
        : "You can add it again later. Anything that was using it falls back to your other key, if you have one.",
      confirmLabel: "Delete key",
      tone: "danger",
      onConfirm: async () => {
        try {
          await apiClient.delete(`/keys/${keyToRemove.id}`);
        } catch (err) {
          throw new Error(err instanceof ApiError ? err.message : "Could not delete the key.");
        }
      },
    });
    setRemoving(false);
    if (ok) {
      setJustValidated(null);
      onDeleted(keyToRemove);
      toast({ tone: "success", title: `${provider} ${slot} key deleted` });
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2 sm:flex-nowrap">
        <input
          type="password"
          aria-label={`${provider} ${slot} API key`}
          autoComplete="off"
          spellCheck={false}
          maxLength={512}
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
        <Button
          type="submit"
          variant="primary"
          loading={loading}
          disabled={!value.trim()}
          aria-label={`Save ${provider} ${slot} key`}
        >
          {loading ? "Checking…" : "Save"}
        </Button>
        {existing && onDeleted && (
          <Button type="button" variant="danger" onClick={handleDelete}
            disabled={loading || removing}
            aria-label={`Delete ${provider} ${slot} key`}
          >
            <TrashIcon size={14} />
            Delete
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
