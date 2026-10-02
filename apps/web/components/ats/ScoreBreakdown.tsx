import { motion } from "framer-motion";
import { Card } from "@/components/ui/Card";
import type { ScoreResponse } from "@/types/ats";

function scoreColor(fraction: number): string {
  if (fraction >= 0.75) return "text-green-600 dark:text-green-400";
  if (fraction >= 0.5) return "text-yellow-600 dark:text-yellow-400";
  return "text-destructive";
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

export function ScoreBreakdown({ result }: { result: ScoreResponse }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="flex flex-col gap-4"
    >
      <Card className="flex flex-col items-center gap-2 p-6">
        <span className="text-sm text-muted-foreground">Composite Score</span>
        <span className={`text-4xl font-bold ${scoreColor(result.composite_score / 100)}`}>
          {result.composite_score}
          <span className="text-lg text-muted-foreground">/100</span>
        </span>
      </Card>

      <Card className="flex flex-col gap-4 p-5">
        <SubScoreBar label="Keyword match" value={result.keyword_score} />
        <SubScoreBar label="Semantic relevance" value={result.semantic_score} />
        <SubScoreBar label="Formatting" value={result.formatting_score} />
      </Card>

      {result.coverage && result.coverage.length > 0 && (
        <Card className="p-5">
          <h3 className="text-sm font-medium">Requirements from the job description</h3>
          <ul className="mt-3 flex flex-col gap-3">
            {result.coverage.map((c) => (
              <li key={`${c.kind}-${c.term}`} className="text-sm">
                <div className="flex items-center gap-2">
                  <span
                    aria-label={c.covered ? "Covered" : "Not covered"}
                    className={c.covered ? "text-green-600 dark:text-green-400" : "text-destructive"}
                  >
                    {c.covered ? "✓" : "✗"}
                  </span>
                  <span className="font-medium">{c.term}</span>
                  <span className="text-xs text-muted-foreground">
                    {c.kind === "must" ? "must-have" : "nice-to-have"}
                    {c.covered && c.section ? ` · found in ${c.section}` : ""}
                  </span>
                </div>
                {c.covered && c.evidence && (
                  <p className="mt-1 line-clamp-2 pl-6 text-xs text-muted-foreground">
                    {c.evidence.replace(/\s+/g, " ")}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </Card>
      )}

      {(result.missing_must_have.length > 0 || result.missing_nice_to_have.length > 0) && (
        <Card className="p-5">
          <h3 className="text-sm font-medium">Missing keywords</h3>
          {result.missing_must_have.length > 0 && (
            <p className="mt-2 text-sm">
              <span className="text-destructive">Must-have: </span>
              {result.missing_must_have.join(", ")}
            </p>
          )}
          {result.missing_nice_to_have.length > 0 && (
            <p className="mt-1 text-sm">
              <span className="text-muted-foreground">Nice-to-have: </span>
              {result.missing_nice_to_have.join(", ")}
            </p>
          )}
        </Card>
      )}

      <Card className="p-5">
        <h3 className="text-sm font-medium">Feedback</h3>
        <p className="mt-2 whitespace-pre-wrap text-sm text-muted-foreground">
          {result.feedback}
        </p>
      </Card>
    </motion.div>
  );
}
