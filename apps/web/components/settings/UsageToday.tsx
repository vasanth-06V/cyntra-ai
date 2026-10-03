"use client";

import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api-client/fastapi";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { RefreshIcon } from "@/components/ui/icons";
import { Skeleton } from "@/components/ui/Skeleton";

interface UsageRow {
  provider: string;
  kind: "chat" | "embed";
  requests: number;
  input_tokens: number;
  output_tokens: number;
  thought_tokens?: number;
}

export function UsageToday() {
  const [rows, setRows] = useState<UsageRow[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    apiClient
      .get<UsageRow[]>("/usage")
      .then((r) => {
        if (!cancelled) setRows(r);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  if (failed) {
    return (
      <Card className="p-5">
        <h2 className="text-sm font-semibold">Used today</h2>
        <p role="alert" className="mt-2 text-sm text-muted-foreground">
          Could not load today&apos;s usage.
        </p>
        <Button
          variant="outline"
          size="sm"
          className="mt-3"
          onClick={() => {
            setFailed(false);
            setRows(null);
            setAttempt((n) => n + 1);
          }}
        >
          <RefreshIcon size={14} />
          Try again
        </Button>
      </Card>
    );
  }

  if (rows === null) {
    return (
      <Card className="p-5" role="status">
        <span className="sr-only">Loading usage…</span>
        <Skeleton className="h-4 w-28" />
        <Skeleton className="mt-3 h-3 w-2/3" />
        <Skeleton className="mt-4 h-10 w-full" />
      </Card>
    );
  }

  // Bars compare each row's tokens with the busiest row, so the heaviest use stands out.
  const totals = rows.map((r) => r.input_tokens + r.output_tokens + (r.thought_tokens ?? 0));
  const max = Math.max(1, ...totals);

  return (
    <Card className="p-5">
      <h2 className="text-sm font-semibold">Used today</h2>
      <p className="mt-0.5 text-xs text-muted-foreground">
        Gemini&apos;s daily quota resets at midnight Pacific time.
      </p>
      {rows.length === 0 ? (
        <p className="mt-3 rounded-lg bg-secondary px-3 py-2.5 text-sm text-muted-foreground">
          No requests yet today.
        </p>
      ) : (
        <ul className="stagger mt-4 flex flex-col gap-3.5">
          {rows.map((r, i) => (
            <li key={`${r.provider}-${r.kind}`} className="text-sm">
              <div className="flex items-baseline justify-between gap-3">
                <span className="font-medium">
                  <span className="capitalize">{r.provider}</span>{" "}
                  <span className="font-normal text-muted-foreground">
                    {r.kind === "embed" ? "embeddings" : "chat"}
                  </span>
                </span>
                <span className="shrink-0 tabular-nums text-muted-foreground">
                  {r.requests} request{r.requests === 1 ? "" : "s"}
                </span>
              </div>
              <div aria-hidden="true" className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-secondary">
                <div
                  className="bar-fill h-full rounded-full bg-primary"
                  style={{ width: `${Math.max(3, (totals[i] / max) * 100)}%` }}
                />
              </div>
              <p className="mt-1 text-xs tabular-nums text-muted-foreground">
                {r.input_tokens.toLocaleString()} in / {r.output_tokens.toLocaleString()} out tokens
                {r.thought_tokens ? ` (+${r.thought_tokens.toLocaleString()} thinking)` : ""}
              </p>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
