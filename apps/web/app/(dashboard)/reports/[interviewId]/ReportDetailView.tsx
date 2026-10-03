"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiClient, ApiError } from "@/lib/api-client/fastapi";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { reportToMarkdown, resultLabel, timeLeft } from "@/lib/reports/format";
import { INTERVIEW_TYPE_LABELS, type InterviewType } from "@/types/interviews";
import type { ReportResponse } from "@/types/reports";

function scoreColor(fraction: number): string {
  if (fraction >= 0.75) return "text-green-600 dark:text-green-400";
  if (fraction >= 0.5) return "text-yellow-600 dark:text-yellow-400";
  return "text-destructive";
}

function Quote({ text }: { text: string | null }) {
  if (!text) return null;
  return <blockquote className="mt-1 border-l-2 border-border pl-3 text-xs italic text-muted-foreground">“{text}”</blockquote>;
}

export function ReportDetailView({ interviewId }: { interviewId: string }) {
  const router = useRouter();
  const [data, setData] = useState<ReportResponse | null>(null);
  const [error, setError] = useState<{ message: string; gone: boolean } | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    apiClient
      .get<ReportResponse>(`/reports/${interviewId}`)
      .then(setData)
      .catch((err) =>
        setError({
          message: err instanceof ApiError ? err.message : "Could not load this report.",
          gone: err instanceof ApiError && (err.status === 404 || err.status === 410),
        })
      );
  }, [interviewId]);

  if (error) {
    return (
      <div className="max-w-xl">
        <p role="alert" className={`text-sm ${error.gone ? "text-muted-foreground" : "text-destructive"}`}>
          {error.message}
        </p>
        <Link href="/reports" className="mt-4 inline-block text-sm underline">
          Back to reports
        </Link>
      </div>
    );
  }
  if (!data) return <p className="text-sm text-muted-foreground">Loading…</p>;

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
    a.click();
    URL.revokeObjectURL(url);
  }

  async function remove() {
    if (!window.confirm("Delete this report now? This cannot be undone.")) return;
    setDeleting(true);
    try {
      await apiClient.delete(`/reports/${interviewId}`);
      router.push("/reports");
    } catch (err) {
      setDeleting(false);
      setError({ message: err instanceof ApiError ? err.message : "Could not delete the report.", gone: false });
    }
  }

  return (
    <article className="mx-auto flex max-w-3xl flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2 print:hidden">
        <Link href="/reports" className="text-sm text-muted-foreground hover:underline">
          ← All reports
        </Link>
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" onClick={() => window.print()}>
            Save as PDF
          </Button>
          <Button type="button" variant="outline" onClick={download}>
            Download text
          </Button>
          <Button type="button" variant="outline" onClick={remove} disabled={deleting}>
            Delete now
          </Button>
        </div>
      </div>

      <header>
        <h1 className="text-2xl font-semibold">Interview report — {typeLabel}</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {new Date(data.created_at).toLocaleString()} · {report.interview.minutes_used} min ·{" "}
          <span className="print:hidden">{timeLeft(data.expires_at)} · </span>
          available until {new Date(data.expires_at).toLocaleDateString()}
        </p>
      </header>

      <Card className="flex flex-col items-center gap-1 p-6 text-center">
        <span className={`text-5xl font-bold ${scoreColor(report.overall_score / 100)}`}>
          {report.overall_score}
          <span className="text-lg text-muted-foreground">/100</span>
        </span>
        <span className="text-sm font-medium">{report.band}</span>
        {report.verdict && <p className="mt-2 max-w-xl text-sm text-muted-foreground">{report.verdict}</p>}
      </Card>

      <Card className="p-5">
        <h2 className="text-sm font-medium">Skills</h2>
        <ul className="mt-3 flex flex-col gap-4">
          {report.dimensions.map((d) => (
            <li key={d.key}>
              <div className="flex items-center justify-between text-sm">
                <span>{d.label}</span>
                <span className={`font-medium ${scoreColor(d.score / 5)}`}>{d.score}/5</span>
              </div>
              <div className="mt-1 h-2 overflow-hidden rounded-full bg-secondary">
                <div className="h-full rounded-full bg-primary" style={{ width: `${(d.score / 5) * 100}%` }} />
              </div>
              {d.reason && <p className="mt-1 text-sm text-muted-foreground">{d.reason}</p>}
              <Quote text={d.quote} />
            </li>
          ))}
        </ul>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        {[
          { title: "What went well", items: report.strengths },
          { title: "What to improve", items: report.improvements },
        ].map((group) => (
          <Card key={group.title} className="p-5">
            <h2 className="text-sm font-medium">{group.title}</h2>
            {group.items.length === 0 ? (
              <p className="mt-2 text-sm text-muted-foreground">Nothing specific to add.</p>
            ) : (
              <ul className="mt-3 flex flex-col gap-3">
                {group.items.map((item, i) => (
                  <li key={i} className="text-sm">
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
          <h2 className="text-sm font-medium">Coding round</h2>
          <ul className="mt-3 flex flex-col gap-4">
            {report.coding.map((c) => (
              <li key={c.problem} className="text-sm">
                <p className="font-medium">
                  Problem {c.problem} · {c.language}, {c.line_count} lines ·{" "}
                  <span className={c.result === "correct" || c.result === "mostly_correct" ? "text-green-600 dark:text-green-400" : "text-destructive"}>
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
          <h2 className="text-sm font-medium">Phase by phase</h2>
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
          <h2 className="text-sm font-medium">Next steps</h2>
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
