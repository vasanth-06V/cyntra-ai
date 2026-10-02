import { motion } from "framer-motion";
import { Card } from "@/components/ui/Card";
import { parseFeedback } from "@/lib/ats/feedback";
import type { RequirementCoverage, ScoreResponse } from "@/types/ats";

function scoreColor(fraction: number): string {
  if (fraction >= 0.75) return "text-green-600 dark:text-green-400";
  if (fraction >= 0.5) return "text-yellow-600 dark:text-yellow-400";
  return "text-destructive";
}

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
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">{label}</span>
        <span className={`font-medium ${scoreColor(value)}`}>{pct}%</span>
      </div>
      <div className="mt-1 h-2 overflow-hidden rounded-full bg-secondary">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.5, ease: "easeOut" }}
          className="h-full rounded-full bg-primary"
        />
      </div>
    </div>
  );
}

function Chips({ items, tone }: { items: string[]; tone: "must" | "nice" }) {
  const style =
    tone === "must"
      ? "border-destructive/40 bg-destructive/10 text-destructive"
      : "border-border bg-secondary text-muted-foreground";
  return (
    <div className="mt-2 flex flex-wrap gap-2">
      {items.map((t) => (
        <span key={t} className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${style}`}>
          {t}
        </span>
      ))}
    </div>
  );
}

function RequirementRow({ c }: { c: RequirementCoverage }) {
  const head = (
    <div className="flex items-center gap-2 text-sm">
      <span
        aria-label={c.covered ? "Covered" : "Not covered"}
        className={c.covered ? "text-green-600 dark:text-green-400" : "text-destructive"}
      >
        {c.covered ? "✓" : "✗"}
      </span>
      <span className="font-medium">{c.term}</span>
      {c.covered && c.section && (
        <span className="text-xs text-muted-foreground">· {c.section}</span>
      )}
    </div>
  );
  if (!c.covered || !c.evidence) return <li>{head}</li>;
  return (
    <li>
      <details>
        <summary className="cursor-pointer list-none [&::-webkit-details-marker]:hidden">
          {head}
        </summary>
        <p className="mt-1 pl-6 text-xs text-muted-foreground">
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
        <span className="text-xs text-muted-foreground">
          {covered} of {items.length} covered
        </span>
      </div>
      <ul className="mt-2 flex flex-col gap-2">
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
  const hasMissing =
    result.missing_must_have.length > 0 || result.missing_nice_to_have.length > 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="flex flex-col gap-4"
    >
      <div className="grid gap-4 md:grid-cols-[220px_1fr]">
        <Card className="flex flex-col items-center justify-center gap-1 p-6">
          <span className="text-sm text-muted-foreground">Composite score</span>
          <span className={`text-5xl font-bold ${scoreColor(result.composite_score / 100)}`}>
            {result.composite_score}
            <span className="text-lg text-muted-foreground">/100</span>
          </span>
          <span className="text-sm font-medium">{verdict(result.composite_score)}</span>
        </Card>
        <Card className="flex flex-col justify-center gap-4 p-5">
          <SubScoreBar label="Keyword match" value={result.keyword_score} />
          <SubScoreBar label="Semantic relevance" value={result.semantic_score} />
          <SubScoreBar label="Formatting" value={result.formatting_score} />
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-5">
          <h3 className="text-sm font-medium">How to improve</h3>
          {tips.length > 0 ? (
            <ol className="mt-3 flex flex-col gap-3">
              {tips.map((tip, i) => (
                <li key={i} className="flex gap-3 text-sm">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
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
              <h3 className="text-sm font-medium">Missing keywords</h3>
              {result.missing_must_have.length > 0 && (
                <div className="mt-2">
                  <span className="text-xs text-muted-foreground">Must-have</span>
                  <Chips items={result.missing_must_have} tone="must" />
                </div>
              )}
              {result.missing_nice_to_have.length > 0 && (
                <div className="mt-3">
                  <span className="text-xs text-muted-foreground">Nice-to-have</span>
                  <Chips items={result.missing_nice_to_have} tone="nice" />
                </div>
              )}
            </Card>
          )}

          {coverage.length > 0 && (
            <Card className="flex flex-col gap-4 p-5">
              <h3 className="text-sm font-medium">Requirements from the job description</h3>
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
