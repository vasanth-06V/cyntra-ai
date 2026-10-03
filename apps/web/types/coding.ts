export type ProblemState = {
  enabled: boolean;
  active: boolean;
  phase: string | null;
  problem_number?: number | null;
  total_problems?: number | null;
  question?: string | null;
  submission?: { language: string; line_count: number; status: "review" | "done" } | null;
  review_job_id?: string | null;
};

export type SubmissionStarted = { job_id: string; submission_id: string };
