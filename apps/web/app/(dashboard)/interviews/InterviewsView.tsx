"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiClient, ApiError } from "@/lib/api-client/fastapi";
import { Alert } from "@/components/ui/Alert";
import { Badge, type Tone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { ListSkeleton } from "@/components/ui/Skeleton";
import { ChevronRightIcon, MicIcon } from "@/components/ui/icons";
import { INTERVIEW_TYPE_LABELS, type Interview, type InterviewStatus } from "@/types/interviews";

const STATUS_TONE: Record<InterviewStatus, Tone> = {
  setting_up: "info",
  in_progress: "brand",
  completed: "success",
  aborted: "neutral",
};

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
      <PageHeader
        title="Interviews"
        description="Timed mock interviews built from your resume and a job description."
        actions={
          <Link href="/interviews/setup" className="rounded-lg">
            <Button>Start new interview</Button>
          </Link>
        }
      />

      {loading ? (
        <ListSkeleton className="mt-6" rows={4} />
      ) : error ? (
        <Alert role="alert" className="mt-6">
          {error}
        </Alert>
      ) : interviews.length === 0 ? (
        <EmptyState className="mt-6" icon={<MicIcon size={20} />} title="No interviews yet">
          No interviews yet -- start one above.
        </EmptyState>
      ) : (
        <div className="stagger mt-6 flex flex-col gap-2">
          {interviews.map((iv) => (
            <Link key={iv.id} href={`/interviews/${iv.id}`} className="group block rounded-xl">
              <Card interactive className="flex items-center justify-between gap-3 p-4">
                <div className="flex min-w-0 items-center gap-3.5">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent text-accent-foreground">
                    <MicIcon size={18} />
                  </span>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{INTERVIEW_TYPE_LABELS[iv.type]}</p>
                    <p className="text-xs text-muted-foreground tabular-nums">
                      {new Date(iv.created_at).toLocaleString()}
                    </p>
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <Badge tone={STATUS_TONE[iv.status] ?? "neutral"} className="capitalize">
                    {iv.status.replace(/_/g, " ")}
                  </Badge>
                  <ChevronRightIcon
                    size={18}
                    className="text-muted-foreground transition-transform duration-200 group-hover:translate-x-0.5 group-hover:text-primary motion-reduce:transform-none"
                  />
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
