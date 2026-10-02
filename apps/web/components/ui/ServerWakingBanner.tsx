"use client";

import { useSyncExternalStore } from "react";
import { serverStatus } from "@/lib/api-client/server-status";

/** Shown while the API is unreachable and requests are being retried. */
export function ServerWakingBanner() {
  const waking = useSyncExternalStore(
    serverStatus.subscribe,
    serverStatus.getSnapshot,
    serverStatus.getServerSnapshot
  );

  if (!waking) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="border-b border-border bg-secondary px-6 py-2 text-center text-sm text-muted-foreground"
    >
      Waking the server — this can take up to a minute the first time. Hang tight…
    </div>
  );
}
