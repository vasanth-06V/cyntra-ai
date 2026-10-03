"use client";

import { useState } from "react";
import { Card } from "@/components/ui/Card";
import { ProviderKeyForm } from "./ProviderKeyForm";
import { PROVIDER_INFO, type ProviderKey, type ProviderName } from "@/types/keys";

export function ProviderKeySection({
  provider,
  keys,
  onKeysChange,
  required = false,
}: {
  provider: ProviderName;
  keys: ProviderKey[];
  onKeysChange: (keys: ProviderKey[]) => void;
  required?: boolean;
}) {
  const info = PROVIDER_INFO[provider];
  const [showBackup, setShowBackup] = useState(
    keys.some((k) => k.provider === provider && k.slot === "backup")
  );

  const primary = keys.find((k) => k.provider === provider && k.slot === "primary");
  const backup = keys.find((k) => k.provider === provider && k.slot === "backup");

  function upsertKey(saved: ProviderKey) {
    const others = keys.filter(
      (k) => !(k.provider === saved.provider && k.slot === saved.slot)
    );
    onKeysChange([...others, saved]);
  }

  function removeKey(gone: ProviderKey) {
    onKeysChange(keys.filter((k) => k.id !== gone.id));
  }

  return (
    <Card className="p-5">
      <div className="flex items-center justify-between">
        <h3 className="font-medium">
          {info.label}
          {required && <span className="ml-2 text-xs text-destructive">Required</span>}
        </h3>
        <a
          href={info.getKeyUrl}
          target="_blank"
          rel="noreferrer"
          className="text-xs text-primary underline-offset-4 hover:underline"
        >
          Get your {info.label} key
        </a>
      </div>
      <p className="mt-1 text-sm text-muted-foreground">{info.instructions}</p>

      <div className="mt-4">
        <ProviderKeyForm
          provider={provider}
          slot="primary"
          existing={primary}
          onSaved={upsertKey}
          onDeleted={removeKey}
        />
      </div>

      {showBackup || backup ? (
        <div className="mt-4 border-t border-border pt-4">
          <p className="mb-2 text-xs text-muted-foreground">
            Backup key (used automatically if the primary hits a rate limit)
          </p>
          <ProviderKeyForm
            provider={provider}
            slot="backup"
            existing={backup}
            onSaved={upsertKey}
            onDeleted={removeKey}
          />
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setShowBackup(true)}
          className="mt-3 text-sm text-muted-foreground underline-offset-4 hover:underline cursor-pointer"
        >
          + Add a backup key
        </button>
      )}
    </Card>
  );
}
