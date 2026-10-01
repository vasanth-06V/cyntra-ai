import type { ProviderName } from "./keys";

export type ScoreRequest = {
  resume_id: string;
  jd_text: string;
  provider: ProviderName;
};

export type ScoreResponse = {
  composite_score: number;
  keyword_score: number;
  semantic_score: number;
  formatting_score: number;
  feedback: string;
  missing_must_have: string[];
  missing_nice_to_have: string[];
};
