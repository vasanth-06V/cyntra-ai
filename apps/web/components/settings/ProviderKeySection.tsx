"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/Badge";
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
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
        <div className="flex items-center gap-3">
          <span
            aria-hidden="true"
            className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent text-sm font-semibold text-accent-foreground"
          >
            {info.label.charAt(0)}
          </span>
          <h3 className="flex flex-wrap items-center gap-2 font-semibold tracking-tight">
            {info.label}
            {required && <Badge tone="warning">Required</Badge>}
            {primary ? (
              primary.is_valid ? (
                <Badge tone="success">Connected</Badge>
              ) : (
                <Badge tone="danger">Needs attention</Badge>
              )
            ) : (
              <Badge>Not connected</Badge>
            )}
          </h3>
        </div>
        <a
          href={info.getKeyUrl}
          target="_blank"
          rel="noreferrer"
          className="text-xs font-medium text-primary underline-offset-4 hover:underline"
        >
          Get your {info.label} key
        </a>
      </div>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">{info.instructions}</p>

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
          <p className="mb-2 text-xs font-medium text-muted-foreground">
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
          className="mt-3 cursor-pointer text-sm font-medium text-primary underline-offset-4 hover:underline"
        >
          + Add a backup key
        </button>
      )}
    </Card>
  );
}
