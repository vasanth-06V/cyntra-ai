"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiClient, ApiError } from "@/lib/api-client/fastapi";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { INTERVIEW_TYPE_LABELS, type Interview } from "@/types/interviews";

export function InterviewsView() {
  const [interviews, setInterviews] = useState<Interview[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiClient
      .get<Interview[]>("/interviews")
      .then(setInterviews)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Could not load interviews.")
      )
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Interviews</h1>
        <Link href="/interviews/setup">
          <Button>Start new interview</Button>
        </Link>
      </div>

      {loading ? (
        <p className="mt-6 text-sm text-muted-foreground">Loading…</p>
      ) : error ? (
        <p className="mt-6 text-sm text-destructive">{error}</p>
      ) : interviews.length === 0 ? (
        <div className="mt-6 rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
          No interviews yet -- start one above.
        </div>
      ) : (
        <div className="mt-6 flex flex-col gap-2">
          {interviews.map((iv) => (
            <Link key={iv.id} href={`/interviews/${iv.id}`}>
              <Card className="flex items-center justify-between p-4 transition-colors hover:bg-secondary">
                <div>
                  <p className="text-sm font-medium">{INTERVIEW_TYPE_LABELS[iv.type]}</p>
                  <p className="text-xs text-muted-foreground">
                    {new Date(iv.created_at).toLocaleString()}
                  </p>
                </div>
                <span className="text-xs capitalize text-muted-foreground">
                  {iv.status.replace(/_/g, " ")}
                </span>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
