"use client";

import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api-client/fastapi";

interface UsageRow {
  provider: string;
  kind: "chat" | "embed";
  requests: number;
  input_tokens: number;
  output_tokens: number;
}

export function UsageToday() {
  const [rows, setRows] = useState<UsageRow[] | null>(null);

  useEffect(() => {
    apiClient
      .get<UsageRow[]>("/usage")
      .then(setRows)
      .catch(() => setRows([]));
  }, []);

  if (rows === null) return null;

  return (
    <div className="rounded-lg border border-border p-4">
      <h2 className="text-sm font-medium">Used today (UTC)</h2>
      {rows.length === 0 ? (
        <p className="mt-1 text-sm text-muted-foreground">No requests yet today.</p>
      ) : (
        <ul className="mt-2 flex flex-col gap-1 text-sm text-muted-foreground">
          {rows.map((r) => (
            <li key={`${r.provider}-${r.kind}`}>
              <span className="capitalize">{r.provider}</span>{" "}
              {r.kind === "embed" ? "embeddings" : "chat"}: {r.requests} request
              {r.requests === 1 ? "" : "s"} · {r.input_tokens.toLocaleString()} in /{" "}
              {r.output_tokens.toLocaleString()} out tokens
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
