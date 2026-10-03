export type ReportDimension = {
  key: string;
  label: string;
  score: number;
  reason: string;
  quote: string | null;
};

export type ReportCoding = {
  problem: number;
  language: string;
  line_count: number;
  result: "correct" | "mostly_correct" | "incorrect" | "incomplete";
  approach: string;
  issues: string[];
  edge_cases_missed: string[];
  candidate_complexity: string;
  reference_complexity: string;
};

export type ReportData = {
  version: number;
  interview: { id: string; type: string; started_at: string | null; minutes_used: number };
  overall_score: number;
  band: string;
  verdict: string;
  dimensions: ReportDimension[];
  strengths: { point: string; quote: string | null }[];
  improvements: { point: string; quote: string | null }[];
  phase_notes: { phase: string; note: string }[];
  next_steps: string[];
  coding: ReportCoding[];
  stats: { answers: number; avg_words: number; phases: { phase: string; answers: number }[]; omitted_turns: number };
  disclaimer: string;
};

export type ReportSummary = {
  interview_id: string;
  interview_type: string;
  overall_score: number;
  created_at: string;
  expires_at: string;
};

export type ReportResponse = ReportSummary & { report: ReportData };
