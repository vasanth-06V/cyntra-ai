"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiClient, ApiError } from "@/lib/api-client/fastapi";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { ScoreRing } from "@/components/ui/ScoreRing";
import { ListSkeleton } from "@/components/ui/Skeleton";
import { ReportIcon } from "@/components/ui/icons";
import { timeLeft } from "@/lib/reports/format";
import { useReportGeneration } from "@/lib/reports/useReportGeneration";
import { INTERVIEW_TYPE_LABELS, type Interview, type InterviewType } from "@/types/interviews";
import type { ReportSummary } from "@/types/reports";

const typeLabel = (t: string) => INTERVIEW_TYPE_LABELS[t as InterviewType] ?? t;

export function ReportsView() {
  const router = useRouter();
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [interviews, setInterviews] = useState<Interview[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const openReport = useCallback((id: string) => router.push(`/reports/${id}`), [router]);
  const generation = useReportGeneration(openReport);

  useEffect(() => {
    Promise.all([
      apiClient.get<ReportSummary[]>("/reports"),
      apiClient.get<Interview[]>("/interviews"),
    ])
      .then(([r, i]) => {
        setReports(r);
        setInterviews(i.filter((x) => x.status === "completed"));
      })
      .catch((err) =>
        setLoadError(err instanceof ApiError ? err.message : "Could not load your reports.")
      )
      .finally(() => setLoading(false));
  }, []);

  const withReport = new Set(reports.map((r) => r.interview_id));
  const waiting = interviews.filter((i) => !withReport.has(i.id));

  return (
    <div>
      <PageHeader
        title="Reports"
        description="A report is available for 7 days after it is made. Download it before it expires."
      />

      {loading ? (
        <div className="mt-6 flex max-w-3xl flex-col gap-8">
          <ListSkeleton rows={3} />
        </div>
      ) : loadError ? (
        <Alert role="alert" className="mt-6">
          {loadError}
        </Alert>
      ) : (
        <div className="mt-6 flex max-w-3xl flex-col gap-10">
          <section aria-label="Your reports">
            <h2 className="text-sm font-semibold tracking-tight">Your reports</h2>
            {reports.length === 0 ? (
              <EmptyState className="mt-3" icon={<ReportIcon size={20} />} title="No reports yet">
                No reports yet. Finish an interview, then get its report below.
              </EmptyState>
            ) : (
              <div className="stagger mt-3 flex flex-col gap-2">
                {reports.map((r) => (
                  <Link key={r.interview_id} href={`/reports/${r.interview_id}`} className="group block rounded-xl">
                    <Card interactive className="flex items-center justify-between gap-4 p-4">
                      <div className="flex min-w-0 items-center gap-4">
                        <ScoreRing value={r.overall_score} size={52} stroke={5} showValue={false} />
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium">{typeLabel(r.interview_type)}</p>
                          <p className="text-xs text-muted-foreground tabular-nums">
                            {new Date(r.created_at).toLocaleString()} · {timeLeft(r.expires_at)}
                          </p>
                        </div>
                      </div>
                      <span className="shrink-0 text-lg font-semibold tabular-nums">
                        {r.overall_score}
                        <span className="text-xs font-normal text-muted-foreground">/100</span>
                      </span>
                    </Card>
                  </Link>
                ))}
              </div>
            )}
          </section>

          <section aria-label="Completed interviews without a report">
            <h2 className="text-sm font-semibold tracking-tight">Completed interviews</h2>
            {waiting.length === 0 ? (
              <p className="mt-2 text-sm text-muted-foreground">
                Every completed interview already has a report.
              </p>
            ) : (
              <div className="stagger mt-3 flex flex-col gap-2">
                {waiting.map((i) => {
                  const busy = generation.busyId === i.id;
                  return (
                    <Card key={i.id} className="flex items-center justify-between gap-3 p-4">
                      <div>
                        <p className="text-sm font-medium">{typeLabel(i.type)}</p>
                        <p className="text-xs text-muted-foreground tabular-nums">
                          {new Date(i.created_at).toLocaleString()}
                        </p>
                        {busy && (
                          <p role="status" className="mt-1 text-xs text-muted-foreground">
                            {generation.progress ?? "Working…"}
                          </p>
                        )}
                      </div>
                      <Button
                        type="button"
                        variant="outline"
                        loading={busy}
                        disabled={generation.busyId !== null}
                        onClick={() => void generation.start(i.id)}
                      >
                        {busy ? "Writing…" : "Get my report"}
                      </Button>
                    </Card>
                  );
                })}
              </div>
            )}
            {generation.error && (
              <Alert role="alert" className="mt-3">
                {generation.error}
              </Alert>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
