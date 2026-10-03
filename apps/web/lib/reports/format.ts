import type { ReportData } from "@/types/reports";

const RESULT_LABELS: Record<string, string> = {
  correct: "Correct",
  mostly_correct: "Mostly correct",
  incorrect: "Incorrect",
  incomplete: "Incomplete",
};

export const resultLabel = (result: string) => RESULT_LABELS[result] ?? result;

const pretty = (s: string) => s.replace(/_/g, " ");

/** "6 days 23 hours left", "3 hours left", "under an hour left", or "Expired". */
export function timeLeft(expiresAt: string, now: number = Date.now()): string {
  const ms = new Date(expiresAt).getTime() - now;
  if (!(ms > 0)) return "Expired";
  const hours = Math.floor(ms / 3_600_000);
  if (hours < 1) return "under an hour left";
  const days = Math.floor(hours / 24);
  const rest = hours % 24;
  if (days === 0) return `${hours} hour${hours === 1 ? "" : "s"} left`;
  return `${days} day${days === 1 ? "" : "s"}${rest ? ` ${rest} hour${rest === 1 ? "" : "s"}` : ""} left`;
}

/** The report as Markdown, for the "download as text" button. */
export function reportToMarkdown(
  report: ReportData,
  meta: { typeLabel: string; createdAt: string; expiresAt: string }
): string {
  const out: string[] = [];
  out.push(`# Interview report — ${meta.typeLabel}`);
  out.push(
    `Created ${new Date(meta.createdAt).toLocaleString()} · available until ${new Date(meta.expiresAt).toLocaleString()}`
  );
  out.push("");
  out.push(`## Overall: ${report.overall_score}/100 (${report.band})`);
  if (report.verdict) out.push(report.verdict);
  out.push("");

  out.push("## Skills");
  for (const d of report.dimensions) {
    out.push(`- **${d.label}: ${d.score}/5** — ${d.reason}${d.quote ? ` _“${d.quote}”_` : ""}`);
  }
  out.push("");

  const list = (title: string, items: { point: string; quote: string | null }[]) => {
    if (!items.length) return;
    out.push(`## ${title}`);
    for (const i of items) out.push(`- ${i.point}${i.quote ? ` _“${i.quote}”_` : ""}`);
    out.push("");
  };
  list("What went well", report.strengths);
  list("What to improve", report.improvements);

  if (report.coding.length) {
    out.push("## Coding round");
    for (const c of report.coding) {
      out.push(`### Problem ${c.problem} — ${c.language}, ${c.line_count} lines — ${resultLabel(c.result)}`);
      if (c.approach) out.push(`Approach: ${pretty(c.approach)}`);
      if (c.candidate_complexity || c.reference_complexity) {
        out.push(`Complexity: yours ${c.candidate_complexity || "n/a"}; reference ${c.reference_complexity || "n/a"}`);
      }
      for (const issue of c.issues) out.push(`- Issue: ${issue}`);
      for (const edge of c.edge_cases_missed) out.push(`- Missed edge case: ${edge}`);
      out.push("");
    }
  }

  if (report.phase_notes.length) {
    out.push("## Phase by phase");
    for (const n of report.phase_notes) out.push(`- **${pretty(n.phase)}**: ${n.note}`);
    out.push("");
  }
  if (report.next_steps.length) {
    out.push("## Next steps");
    for (const s of report.next_steps) out.push(`- ${s}`);
    out.push("");
  }
  out.push(`_${report.disclaimer}_`);
  return out.join("\n");
}
