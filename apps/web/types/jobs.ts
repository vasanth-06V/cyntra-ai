export type JobStatus = "queued" | "running" | "succeeded" | "failed";

export type Job = {
  id: string;
  kind: string;
  status: JobStatus;
  progress: string | null;
  result: Record<string, unknown> | null;
  error: { code: string; message: string; status: number } | null;
  subject_id: string | null;
  created_at: string;
};

export type SetupStarted = { job_id: string; interview_id: string };
