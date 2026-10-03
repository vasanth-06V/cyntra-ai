import { motion } from "framer-motion";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { ScoreRing } from "@/components/ui/ScoreRing";
import { CheckIcon, ChevronRightIcon, XIcon } from "@/components/ui/icons";
import { scoreTone, toneText } from "@/components/ui/score";
import { parseFeedback } from "@/lib/ats/feedback";
import type { RequirementCoverage, ScoreResponse } from "@/types/ats";

function verdict(score: number): string {
  if (score >= 80) return "Strong match";
  if (score >= 60) return "Good match, some gaps";
  if (score >= 40) return "Partial match";
  return "Weak match";
}

function SubScoreBar({ label, value }: { label: string; value: number }) {
  const pct = Math.round(value * 100);
  return (
    <div>
      <div className="flex items-baseline justify-between text-sm">
        <span className="font-medium">{label}</span>
        <span className={`font-semibold tabular-nums ${toneText[scoreTone(value)]}`}>{pct}%</span>
      </div>
      <ProgressBar fraction={value} className="mt-2" />
    </div>
  );
}

function Chips({ items, tone }: { items: string[]; tone: "must" | "nice" }) {
  return (
    <div className="mt-2 flex flex-wrap gap-2">
      {items.map((t) => (
        <Badge key={t} tone={tone === "must" ? "danger" : "neutral"}>
          {t}
        </Badge>
      ))}
    </div>
  );
}

function RequirementRow({ c }: { c: RequirementCoverage }) {
  const head = (
    <div className="flex items-center gap-2.5 text-sm">
      <span
        aria-label={c.covered ? "Covered" : "Not covered"}
        role="img"
        className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full ${
          c.covered ? "bg-success-soft text-success" : "bg-destructive-soft text-destructive"
        }`}
      >
        {c.covered ? <CheckIcon size={12} strokeWidth={2.5} /> : <XIcon size={12} strokeWidth={2.5} />}
      </span>
      <span className="font-medium">{c.term}</span>
      {c.covered && c.section && <span className="text-xs text-muted-foreground">· {c.section}</span>}
    </div>
  );
  if (!c.covered || !c.evidence) return <li>{head}</li>;
  return (
    <li>
      <details className="group">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-2 rounded-md [&::-webkit-details-marker]:hidden">
          {head}
          <ChevronRightIcon
            size={14}
            className="shrink-0 text-muted-foreground transition-transform duration-200 group-open:rotate-90"
          />
        </summary>
        <p className="mt-1.5 rounded-lg bg-secondary px-3 py-2 text-xs leading-5 text-muted-foreground">
          {c.evidence.replace(/\s+/g, " ")}
        </p>
      </details>
    </li>
  );
}

function RequirementGroup({ title, items }: { title: string; items: RequirementCoverage[] }) {
  if (items.length === 0) return null;
  const covered = items.filter((c) => c.covered).length;
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <h4 className="text-sm font-medium">{title}</h4>
        <span className="text-xs text-muted-foreground tabular-nums">
          {covered} of {items.length} covered
        </span>
      </div>
      <ul className="mt-2.5 flex flex-col gap-2.5">
        {items.map((c) => (
          <RequirementRow key={`${c.kind}-${c.term}`} c={c} />
        ))}
      </ul>
    </div>
  );
}

export function ScoreBreakdown({ result }: { result: ScoreResponse }) {
  const tips = parseFeedback(result.feedback);
  const coverage = result.coverage ?? [];
  const hasMissing = result.missing_must_have.length > 0 || result.missing_nice_to_have.length > 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
      className="flex flex-col gap-4"
    >
      <div className="grid gap-4 md:grid-cols-[260px_1fr]">
        <Card tone="raised" className="flex flex-col items-center justify-center gap-3 p-6">
          <span className="text-xs font-medium uppercase tracking-[0.08em] text-muted-foreground">
            Composite score
          </span>
          <ScoreRing value={result.composite_score} size={160}>
            out of 100
          </ScoreRing>
          <span className="text-center text-sm font-semibold">{verdict(result.composite_score)}</span>
        </Card>
        <Card className="flex flex-col justify-center gap-5 p-5 sm:p-6">
          <SubScoreBar label="Keyword match" value={result.keyword_score} />
          <SubScoreBar label="Semantic relevance" value={result.semantic_score} />
          <SubScoreBar label="Formatting" value={result.formatting_score} />
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-5">
          <h3 className="text-sm font-semibold">How to improve</h3>
          {tips.length > 0 ? (
            <ol className="mt-4 flex flex-col gap-3.5">
              {tips.map((tip, i) => (
                <li key={i} className="flex gap-3 text-sm">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent text-xs font-semibold text-accent-foreground">
                    {i + 1}
                  </span>
                  <span className="leading-6">{tip}</span>
                </li>
              ))}
            </ol>
          ) : (
            <p className="mt-2 text-sm text-muted-foreground">No suggestions this time.</p>
          )}
        </Card>

        <div className="flex flex-col gap-4">
          {hasMissing && (
            <Card className="p-5">
              <h3 className="text-sm font-semibold">Missing keywords</h3>
              {result.missing_must_have.length > 0 && (
                <div className="mt-3">
                  <span className="text-xs font-medium text-muted-foreground">Must-have</span>
                  <Chips items={result.missing_must_have} tone="must" />
                </div>
              )}
              {result.missing_nice_to_have.length > 0 && (
                <div className="mt-4">
                  <span className="text-xs font-medium text-muted-foreground">Nice-to-have</span>
                  <Chips items={result.missing_nice_to_have} tone="nice" />
                </div>
              )}
            </Card>
          )}

          {coverage.length > 0 && (
            <Card className="flex flex-col gap-5 p-5">
              <h3 className="text-sm font-semibold">Requirements from the job description</h3>
              <RequirementGroup title="Must-have" items={coverage.filter((c) => c.kind === "must")} />
              <RequirementGroup title="Nice-to-have" items={coverage.filter((c) => c.kind === "nice")} />
              <p className="text-xs text-muted-foreground">
                Click a covered requirement to see where it appears in your resume.
              </p>
            </Card>
          )}
        </div>
      </div>
    </motion.div>
  );
}
