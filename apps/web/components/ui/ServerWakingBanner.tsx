"use client";

import { useSyncExternalStore } from "react";
import { serverStatus } from "@/lib/api-client/server-status";
import { Spinner } from "./Spinner";

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
      className="flex animate-fade-in items-center justify-center gap-2 border-b border-info/25 bg-info-soft px-6 py-2 text-center text-sm text-info print:hidden"
    >
      <Spinner size={14} />
      Waking the server — this can take up to a minute the first time. Hang tight…
    </div>
  );
}
