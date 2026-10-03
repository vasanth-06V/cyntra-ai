"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiClient, ApiError } from "@/lib/api-client/fastapi";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { useConfirm } from "@/components/ui/ConfirmProvider";
import { ListRow } from "@/components/ui/ListRow";
import { useToast } from "@/components/ui/Toast";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { ScoreRing } from "@/components/ui/ScoreRing";
import { ListSkeleton } from "@/components/ui/Skeleton";
import { ReportIcon, RefreshIcon, TrashIcon } from "@/components/ui/icons";
import { timeLeft } from "@/lib/reports/format";
import { useReportGeneration } from "@/lib/reports/useReportGeneration";
import { INTERVIEW_TYPE_LABELS, type Interview, type InterviewType } from "@/types/interviews";
import type { ReportSummary } from "@/types/reports";

const typeLabel = (t: string) => INTERVIEW_TYPE_LABELS[t as InterviewType] ?? t;

export function ReportsView() {
  const router = useRouter();
  const confirm = useConfirm();
  const { toast } = useToast();
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [interviews, setInterviews] = useState<Interview[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

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
        setLoadError(null);
      })
      .catch((err) =>
        setLoadError(err instanceof ApiError ? err.message : "Could not load your reports.")
      )
      .finally(() => setLoading(false));
  }, [attempt]);

  async function handleDelete(r: ReportSummary) {
    const ok = await confirm({
      title: "Delete this report?",
      description: `The ${typeLabel(r.interview_type)} report (${r.overall_score}/100) will be removed now instead of after 7 days. The interview stays, so you can write a new report for it.`,
      confirmLabel: "Delete report",
      tone: "danger",
      onConfirm: async () => {
        try {
          await apiClient.delete(`/reports/${r.interview_id}`);
        } catch (err) {
          throw new Error(err instanceof ApiError ? err.message : "Could not delete the report.");
        }
        setReports((prev) => prev.filter((x) => x.interview_id !== r.interview_id));
      },
    });
    if (ok) toast({ tone: "success", title: "Report deleted" });
  }

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
        <div className="mt-6 flex max-w-3xl flex-col items-start gap-3">
          <Alert role="alert" className="w-full">
            {loadError}
          </Alert>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setLoading(true);
              setAttempt((n) => n + 1);
            }}
          >
            <RefreshIcon size={14} />
            Try again
          </Button>
        </div>
      ) : (
        <div className="mt-6 flex max-w-3xl flex-col gap-10">
          <section aria-label="Your reports">
            <h2 className="text-sm font-semibold tracking-tight">Your reports</h2>
            {reports.length === 0 ? (
              <EmptyState className="mt-3" icon={<ReportIcon size={20} />} title="No reports yet">
                No reports yet. Finish an interview, then get its report below.
              </EmptyState>
            ) : (
              <ul className="stagger mt-3 flex flex-col gap-2">
                {reports.map((r) => (
                  <li key={r.interview_id}>
                    <ListRow
                      href={`/reports/${r.interview_id}`}
                      leading={<ScoreRing value={r.overall_score} size={44} stroke={5} showValue={false} />}
                      title={`${typeLabel(r.interview_type)} report`}
                      meta={`${new Date(r.created_at).toLocaleString()} · ${timeLeft(r.expires_at)}`}
                      trailing={
                        <span className="text-lg font-semibold tabular-nums">
                          {r.overall_score}
                          <span className="text-xs font-normal text-muted-foreground">/100</span>
                        </span>
                      }
                      actions={
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => void handleDelete(r)}
                          aria-label={`Delete ${typeLabel(r.interview_type)} report`}
                          className="text-muted-foreground hover:bg-destructive-soft hover:text-destructive"
                        >
                          <TrashIcon size={14} />
                        </Button>
                      }
                    />
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section aria-label="Completed interviews without a report">
            <h2 className="text-sm font-semibold tracking-tight">Completed interviews</h2>
            {waiting.length === 0 ? (
              <p className="mt-2 text-sm text-muted-foreground">
                Every completed interview already has a report.
              </p>
            ) : (
              <ul className="stagger mt-3 flex flex-col gap-2">
                {waiting.map((i) => {
                  const busy = generation.busyId === i.id;
                  return (
                    <li key={i.id}>
                      <ListRow
                        title={typeLabel(i.type)}
                        meta={new Date(i.created_at).toLocaleString()}
                        badge={
                          busy ? (
                            <span role="status" className="text-xs text-muted-foreground">
                              {generation.progress ?? "Working…"}
                            </span>
                          ) : undefined
                        }
                        actions={
                          <Button
                            type="button"
                            variant="outline"
                            loading={busy}
                            disabled={generation.busyId !== null}
                            onClick={() => void generation.start(i.id)}
                            aria-label={`Get my report for the ${typeLabel(i.type)} interview`}
                          >
                            {busy ? "Writing…" : "Get my report"}
                          </Button>
                        }
                      />
                    </li>
                  );
                })}
              </ul>
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
