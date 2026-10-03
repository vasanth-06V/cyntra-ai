"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiClient, ApiError } from "@/lib/api-client/fastapi";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
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
      <h1 className="text-2xl font-semibold">Reports</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        A report is available for 7 days after it is made. Download it before it expires.
      </p>

      {loading ? (
        <p className="mt-6 text-sm text-muted-foreground">Loading…</p>
      ) : loadError ? (
        <p role="alert" className="mt-6 text-sm text-destructive">
          {loadError}
        </p>
      ) : (
        <div className="mt-6 flex max-w-3xl flex-col gap-8">
          <section aria-label="Your reports">
            <h2 className="text-sm font-medium">Your reports</h2>
            {reports.length === 0 ? (
              <p className="mt-2 rounded-xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
                No reports yet. Finish an interview, then get its report below.
              </p>
            ) : (
              <div className="mt-2 flex flex-col gap-2">
                {reports.map((r) => (
                  <Link key={r.interview_id} href={`/reports/${r.interview_id}`}>
                    <Card className="flex items-center justify-between gap-3 p-4 transition-colors hover:bg-secondary">
                      <div>
                        <p className="text-sm font-medium">{typeLabel(r.interview_type)}</p>
                        <p className="text-xs text-muted-foreground">
                          {new Date(r.created_at).toLocaleString()} · {timeLeft(r.expires_at)}
                        </p>
                      </div>
                      <span className="text-lg font-semibold">
                        {r.overall_score}
                        <span className="text-xs text-muted-foreground">/100</span>
                      </span>
                    </Card>
                  </Link>
                ))}
              </div>
            )}
          </section>

          <section aria-label="Completed interviews without a report">
            <h2 className="text-sm font-medium">Completed interviews</h2>
            {waiting.length === 0 ? (
              <p className="mt-2 text-sm text-muted-foreground">
                Every completed interview already has a report.
              </p>
            ) : (
              <div className="mt-2 flex flex-col gap-2">
                {waiting.map((i) => {
                  const busy = generation.busyId === i.id;
                  return (
                    <Card key={i.id} className="flex items-center justify-between gap-3 p-4">
                      <div>
                        <p className="text-sm font-medium">{typeLabel(i.type)}</p>
                        <p className="text-xs text-muted-foreground">
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
              <p role="alert" className="mt-3 text-sm text-destructive">
                {generation.error}
              </p>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
