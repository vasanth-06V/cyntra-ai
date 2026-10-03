export type InterviewType =
  | "coding"
  | "behavioral"
  | "hr"
  | "ml_ai"
  | "webd"
  | "sde"
  | "system_design"
  | "case_study";

export const INTERVIEW_TYPE_LABELS: Record<InterviewType, string> = {
  coding: "Coding",
  behavioral: "Behavioral",
  hr: "HR",
  ml_ai: "ML / AI",
  webd: "Web Development",
  sde: "SDE (Mixed)",
  system_design: "System Design",
  case_study: "Case Study",
};

export type InterviewProviderName = "gemini" | "groq";

export type InterviewStatus = "setting_up" | "in_progress" | "completed" | "aborted";

export type Interview = {
  id: string;
  type: InterviewType;
  status: InterviewStatus;
  phase: string | null;
  provider: InterviewProviderName;
  resume_id: string;
  started_at: string | null;
  ends_at: string | null;
  created_at: string;
};

export type TranscriptEntry = {
  id: string;
  turn_index: number;
  speaker: "user" | "ai";
  text: string;
  created_at: string;
};

export type TurnResponse = {
  message: string;
  phase: string;
  minutes_remaining: number;
  is_final_phase: boolean;
};

export type QuestionTestCase = { input: string; output: string };

export type Question = {
  id: string;
  type: InterviewType;
  question: string;
  solution_code: string | null;
  solution_language: string | null;
  test_cases: QuestionTestCase[] | null;
  tags: string[] | null;
  difficulty: number | null;
  topic: string | null;
  created_by: string | null;
  created_at: string;
};
