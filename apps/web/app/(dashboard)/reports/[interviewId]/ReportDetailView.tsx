"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiClient, ApiError } from "@/lib/api-client/fastapi";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { useConfirm } from "@/components/ui/ConfirmProvider";
import { useToast } from "@/components/ui/Toast";
import { ArrowLeftIcon, RefreshIcon, TrashIcon } from "@/components/ui/icons";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { ScoreRing } from "@/components/ui/ScoreRing";
import { Skeleton } from "@/components/ui/Skeleton";
import { scoreTone, toneText } from "@/components/ui/score";
import { reportToMarkdown, resultLabel, timeLeft } from "@/lib/reports/format";
import { INTERVIEW_TYPE_LABELS, type InterviewType } from "@/types/interviews";
import type { ReportResponse } from "@/types/reports";

function Quote({ text }: { text: string | null }) {
  if (!text) return null;
  return (
    <blockquote className="mt-1.5 border-l-2 border-primary/40 pl-3 text-xs italic leading-5 text-muted-foreground">
      “{text}”
    </blockquote>
  );
}

export function ReportDetailView({ interviewId }: { interviewId: string }) {
  const router = useRouter();
  const confirm = useConfirm();
  const { toast } = useToast();
  const [data, setData] = useState<ReportResponse | null>(null);
  const [error, setError] = useState<{ message: string; gone: boolean } | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    apiClient
      .get<ReportResponse>(`/reports/${interviewId}`)
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((err) =>
        setError({
          message: err instanceof ApiError ? err.message : "Could not load this report.",
          gone: err instanceof ApiError && (err.status === 404 || err.status === 410),
        })
      );
  }, [interviewId, attempt]);

  if (error) {
    return (
      <div className="max-w-xl">
        <Alert role="alert" tone={error.gone ? "info" : "danger"}>
          {error.message}
        </Alert>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          {!error.gone && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setError(null);
                setAttempt((n) => n + 1);
              }}
            >
              <RefreshIcon size={14} />
              Try again
            </Button>
          )}
          <Link
            href="/reports"
            className="text-sm font-medium text-primary underline-offset-4 hover:underline"
          >
            Back to reports
          </Link>
        </div>
      </div>
    );
  }
  if (!data) {
    return (
      <div role="status" className="mx-auto flex max-w-3xl flex-col gap-4">
        <span className="sr-only">Loading…</span>
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-4 w-1/2" />
        <Skeleton className="h-56 w-full rounded-xl" />
        <Skeleton className="h-40 w-full rounded-xl" />
      </div>
    );
  }

  const { report } = data;
  const typeLabel = INTERVIEW_TYPE_LABELS[data.interview_type as InterviewType] ?? data.interview_type;

  function download() {
    const md = reportToMarkdown(report, {
      typeLabel,
      createdAt: data!.created_at,
      expiresAt: data!.expires_at,
    });
    const url = URL.createObjectURL(new Blob([md], { type: "text/markdown;charset=utf-8" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `interview-report-${interviewId.slice(0, 8)}.md`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    toast({ tone: "success", title: "Report downloaded", description: a.download });
  }

  async function remove() {
    const ok = await confirm({
      title: "Delete this report now?",
      description:
        "It will be removed immediately instead of after 7 days. Use Download text or Save as PDF first if you want to keep a copy. The interview stays, so you can write a new report for it.",
      confirmLabel: "Delete report",
      tone: "danger",
      onConfirm: async () => {
        try {
          await apiClient.delete(`/reports/${interviewId}`);
        } catch (err) {
          throw new Error(err instanceof ApiError ? err.message : "Could not delete the report.");
        }
      },
    });
    if (ok) {
      toast({ tone: "success", title: "Report deleted" });
      router.push("/reports");
    }
  }

  return (
    <article className="stagger mx-auto flex max-w-3xl flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2 print:hidden">
        <Link
          href="/reports"
          className="text-sm font-medium text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
        >
          <ArrowLeftIcon size={14} className="mr-1 inline" />
          All reports
        </Link>
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" size="sm" onClick={() => window.print()}>
            Save as PDF
          </Button>
          <Button type="button" variant="outline" size="sm" onClick={download}>
            Download text
          </Button>
          <Button type="button" variant="danger" size="sm" onClick={remove}>
            <TrashIcon size={14} />
            Delete now
          </Button>
        </div>
      </div>

      <header>
        <h1 className="text-[1.65rem] font-semibold leading-tight tracking-[-0.025em] sm:text-[1.9rem]">
          Interview report — {typeLabel}
        </h1>
        <p className="mt-1.5 text-sm text-muted-foreground tabular-nums">
          {new Date(data.created_at).toLocaleString()} · {report.interview.minutes_used} min ·{" "}
          <span className="print:hidden">{timeLeft(data.expires_at)} · </span>
          available until {new Date(data.expires_at).toLocaleDateString()}
        </p>
      </header>

      <Card tone="raised" className="brand-wash flex flex-col items-center gap-3 p-6 text-center sm:p-8">
        <ScoreRing value={report.overall_score} size={176}>
          out of 100
        </ScoreRing>
        <Badge tone={scoreTone(report.overall_score / 100)} className="text-sm">
          {report.band}
        </Badge>
        {report.verdict && (
          <p className="mt-1 max-w-xl text-sm leading-6 text-muted-foreground">{report.verdict}</p>
        )}
      </Card>

      <Card className="p-5">
        <h2 className="text-sm font-semibold">Skills</h2>
        <ul className="mt-4 flex flex-col gap-5">
          {report.dimensions.map((d) => (
            <li key={d.key}>
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium">{d.label}</span>
                <span className={`font-semibold tabular-nums ${toneText[scoreTone(d.score / 5)]}`}>{d.score}/5</span>
              </div>
              <ProgressBar fraction={d.score / 5} className="mt-2" />
              {d.reason && <p className="mt-2 text-sm leading-6 text-muted-foreground">{d.reason}</p>}
              <Quote text={d.quote} />
            </li>
          ))}
        </ul>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        {[
          { title: "What went well", items: report.strengths, dot: "bg-success" },
          { title: "What to improve", items: report.improvements, dot: "bg-warning" },
        ].map((group) => (
          <Card key={group.title} className="p-5">
            <h2 className="flex items-center gap-2 text-sm font-semibold">
              <span aria-hidden="true" className={`h-2 w-2 rounded-full ${group.dot}`} />
              {group.title}
            </h2>
            {group.items.length === 0 ? (
              <p className="mt-2 text-sm text-muted-foreground">Nothing specific to add.</p>
            ) : (
              <ul className="mt-3 flex flex-col gap-3">
                {group.items.map((item, i) => (
                  <li key={i} className="text-sm leading-6">
                    {item.point}
                    <Quote text={item.quote} />
                  </li>
                ))}
              </ul>
            )}
          </Card>
        ))}
      </div>

      {report.coding.length > 0 && (
        <Card className="p-5">
          <h2 className="text-sm font-semibold">Coding round</h2>
          <ul className="mt-3 flex flex-col gap-4">
            {report.coding.map((c) => (
              <li key={c.problem} className="text-sm">
                <p className="font-medium">
                  Problem {c.problem} · {c.language}, {c.line_count} lines ·{" "}
                  <span className={c.result === "correct" || c.result === "mostly_correct" ? "text-success" : "text-destructive"}>
                    {resultLabel(c.result)}
                  </span>
                </p>
                {(c.candidate_complexity || c.reference_complexity) && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    Complexity: yours {c.candidate_complexity || "n/a"} · reference {c.reference_complexity || "n/a"}
                  </p>
                )}
                {[...c.issues.map((t) => `Issue: ${t}`), ...c.edge_cases_missed.map((t) => `Missed edge case: ${t}`)].map(
                  (line) => (
                    <p key={line} className="mt-1 text-muted-foreground">
                      {line}
                    </p>
                  )
                )}
              </li>
            ))}
          </ul>
        </Card>
      )}

      {report.phase_notes.length > 0 && (
        <Card className="p-5">
          <h2 className="text-sm font-semibold">Phase by phase</h2>
          <ul className="mt-3 flex flex-col gap-2 text-sm">
            {report.phase_notes.map((n) => (
              <li key={n.phase}>
                <span className="font-medium capitalize">{n.phase.replace(/_/g, " ")}:</span>{" "}
                <span className="text-muted-foreground">{n.note}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {report.next_steps.length > 0 && (
        <Card className="p-5">
          <h2 className="text-sm font-semibold">Next steps</h2>
          <ol className="mt-3 list-decimal pl-5 text-sm">
            {report.next_steps.map((s) => (
              <li key={s} className="mt-1">
                {s}
              </li>
            ))}
          </ol>
        </Card>
      )}

      <p className="text-xs text-muted-foreground">{report.disclaimer}</p>
    </article>
  );
}
