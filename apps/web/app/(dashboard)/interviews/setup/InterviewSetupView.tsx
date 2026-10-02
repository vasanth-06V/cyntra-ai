"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { apiClient, ApiError } from "@/lib/api-client/fastapi";
import { Button } from "@/components/ui/Button";
import { LoadingScene } from "@/components/three/LoadingScene";
import {
  INTERVIEW_TYPE_LABELS,
  type InterviewProviderName,
  type InterviewType,
} from "@/types/interviews";
import type { Job, SetupStarted } from "@/types/jobs";
import type { ProviderKey } from "@/types/keys";
import type { Resume } from "@/types/resumes";

const INTERVIEW_TYPES = Object.keys(INTERVIEW_TYPE_LABELS) as InterviewType[];

const POLL_EVERY_MS = 1500;
const GIVE_UP_AFTER_MS = 4 * 60 * 1000;

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export function InterviewSetupView() {
  const router = useRouter();
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [validProviders, setValidProviders] = useState<InterviewProviderName[]>([]);
  const [type, setType] = useState<InterviewType>("coding");
  const [resumeId, setResumeId] = useState("");
  const [provider, setProvider] = useState<InterviewProviderName | undefined>();
  const [jdText, setJdText] = useState("");
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [progress, setProgress] = useState<string | null>(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      fetch("/api/resumes").then((res) => res.json()),
      apiClient.get<ProviderKey[]>("/keys"),
    ])
      .then(([resumeData, keys]: [Resume[], ProviderKey[]]) => {
        const processed = resumeData.filter((r) => r.parsed_text);
        setResumes(processed);
        if (processed[0]) setResumeId(processed[0].id);

        const providers = keys
          .filter(
            (k) =>
              k.slot === "primary" &&
              k.is_valid &&
              (k.provider === "gemini" || k.provider === "groq")
          )
          .map((k) => k.provider as InterviewProviderName);
        setValidProviders(providers);
        setProvider(providers[0]);
      })
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Could not load resumes or keys.")
      )
      .finally(() => setLoading(false));
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!resumeId || !provider || !jdText.trim()) return;

    setStarting(true);
    setProgress(null);
    setError(null);

    try {
      // The server answers at once with a job; setup (questions, brief,
      // opening message) runs in the background and is polled here.
      const started = await apiClient.post<SetupStarted>("/interviews", {
        type,
        provider,
        resume_id: resumeId,
        jd_text: jdText,
      });

      const deadline = Date.now() + GIVE_UP_AFTER_MS;
      while (mounted.current) {
        const job = await apiClient.get<Job>(`/jobs/${started.job_id}`);
        if (job.status === "succeeded") {
          router.push(`/interviews/${started.interview_id}`);
          return;
        }
        if (job.status === "failed") {
          throw new ApiError(
            job.error?.status ?? 500,
            job.error?.message ?? "Could not set up the interview.",
            job.error?.code
          );
        }
        if (Date.now() > deadline) {
          throw new ApiError(504, "Setting up is taking longer than expected -- please try again.");
        }
        setProgress(job.status === "queued" ? "Waiting for a free slot..." : job.progress);
        await sleep(POLL_EVERY_MS);
      }
    } catch (err) {
      if (!mounted.current) return;
      setError(err instanceof ApiError ? err.message : "Could not start the interview.");
      setStarting(false);
    }
  }

  if (starting) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-16 text-center">
        <LoadingScene className="h-64 w-64" />
        <h1 className="text-xl font-semibold">Setting up your interview…</h1>
        <p className="max-w-sm text-sm text-muted-foreground">
          {progress ?? "Analyzing your resume and matching questions to the job description."}
        </p>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold">Start an interview</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        A fixed 1-hour mock interview, personalized to your resume and the job description.
      </p>

      {loading ? (
        <p className="mt-6 text-sm text-muted-foreground">Loading…</p>
      ) : resumes.length === 0 ? (
        <div className="mt-6 rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
          Upload and process a resume first, from the Resumes page.
        </div>
      ) : validProviders.length === 0 ? (
        <div className="mt-6 rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
          Add a valid Gemini or Groq key first, from Settings → API Keys.
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="mt-6 flex max-w-lg flex-col gap-3">
          <select
            value={type}
            onChange={(e) => setType(e.target.value as InterviewType)}
            className="rounded-lg border border-border bg-transparent px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
          >
            {INTERVIEW_TYPES.map((t) => (
              <option key={t} value={t}>
                {INTERVIEW_TYPE_LABELS[t]}
              </option>
            ))}
          </select>

          <select
            value={resumeId}
            onChange={(e) => setResumeId(e.target.value)}
            className="rounded-lg border border-border bg-transparent px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
          >
            {resumes.map((r) => (
              <option key={r.id} value={r.id}>
                {r.file_key.split("/").pop()}
              </option>
            ))}
          </select>

          <select
            value={provider}
            onChange={(e) => setProvider(e.target.value as InterviewProviderName)}
            className="rounded-lg border border-border bg-transparent px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
          >
            {validProviders.map((p) => (
              <option key={p} value={p}>
                {p === "gemini" ? "Gemini" : "Groq"}
              </option>
            ))}
          </select>

          <textarea
            value={jdText}
            onChange={(e) => setJdText(e.target.value)}
            placeholder="Paste the job description here…"
            rows={8}
            className="rounded-lg border border-border bg-transparent px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
          />

          {error && <p className="text-sm text-destructive">{error}</p>}

          <Button
            type="submit"
            disabled={!provider || !jdText.trim()}
            className="self-start"
          >
            Start interview
          </Button>
        </form>
      )}
    </div>
  );
}
