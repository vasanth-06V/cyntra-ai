import type { ProviderName } from "./keys";

export type RequirementCoverage = {
  term: string;
  kind: "must" | "nice";
  covered: boolean;
  strength: number;
  section: string | null;
  evidence: string;
};

export type ScoreResponse = {
  composite_score: number;
  keyword_score: number;
  semantic_score: number;
  formatting_score: number;
  feedback: string;
  missing_must_have: string[];
  missing_nice_to_have: string[];
  coverage?: RequirementCoverage[];
  /** The saved copy of this result (null when it could not be saved). Absent on saved results. */
  history_id?: string | null;
};

/** One saved check. The API keeps the last 10 per resume. */
export type AtsHistoryItem = {
  id: string;
  resume_id: string;
  job_title: string | null;
  jd_excerpt: string | null;
  provider: ProviderName;
  composite_score: number;
  created_at: string;
};

export type AtsHistoryDetail = AtsHistoryItem & { result: ScoreResponse };

export const ATS_HISTORY_KEPT = 10;
