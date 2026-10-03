"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { apiClient, ApiError } from "@/lib/api-client/fastapi";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { FormSkeleton } from "@/components/ui/Skeleton";
import { FileIcon, KeyIcon } from "@/components/ui/icons";
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
      <div className="brand-wash mx-auto flex max-w-xl flex-col items-center justify-center gap-4 rounded-2xl border border-border bg-card px-6 py-12 text-center shadow-md">
        <LoadingScene className="h-56 w-56" />
        <h1 className="text-xl font-semibold tracking-[-0.025em]">Setting up your interview…</h1>
        <p role="status" className="max-w-sm text-sm leading-6 text-muted-foreground">
          {progress ?? "Analyzing your resume and matching questions to the job description."}
        </p>
        <p className="text-xs text-muted-foreground">This usually takes under a minute. You can keep this tab open.</p>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Start an interview"
        description="A fixed 1-hour mock interview, personalized to your resume and the job description."
      />

      {loading ? (
        <FormSkeleton className="mt-6 max-w-xl" />
      ) : resumes.length === 0 ? (
        <>
          {error && (
            <Alert role="alert" className="mt-6">
              {error}
            </Alert>
          )}
          <EmptyState className="mt-6" icon={<FileIcon size={20} />} title="No processed resume yet">
            Upload and process a resume first, from the Resumes page.
          </EmptyState>
        </>
      ) : validProviders.length === 0 ? (
        <EmptyState className="mt-6" icon={<KeyIcon size={20} />} title="No usable key yet">
          Add a valid Gemini or Groq key first, from Settings → API Keys.
        </EmptyState>
      ) : (
        <Card className="mt-6 max-w-xl p-5 sm:p-6">
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label htmlFor="iv-type" className="text-xs font-medium text-muted-foreground">
                Interview type
              </label>
              <select
                id="iv-type"
                value={type}
                onChange={(e) => setType(e.target.value as InterviewType)}
                className="field"
              >
                {INTERVIEW_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {INTERVIEW_TYPE_LABELS[t]}
                  </option>
                ))}
              </select>
            </div>

            <div className="grid gap-4 sm:grid-cols-[1fr_9rem]">
              <div className="flex min-w-0 flex-col gap-1.5">
                <label htmlFor="iv-resume" className="text-xs font-medium text-muted-foreground">
                  Resume
                </label>
                <select
                  id="iv-resume"
                  value={resumeId}
                  onChange={(e) => setResumeId(e.target.value)}
                  className="field"
                >
                  {resumes.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.file_key.split("/").pop()}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex flex-col gap-1.5">
                <label htmlFor="iv-provider" className="text-xs font-medium text-muted-foreground">
                  Model
                </label>
                <select
                  id="iv-provider"
                  value={provider}
                  onChange={(e) => setProvider(e.target.value as InterviewProviderName)}
                  className="field"
                >
                  {validProviders.map((p) => (
                    <option key={p} value={p}>
                      {p === "gemini" ? "Gemini" : "Groq"}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor="iv-jd" className="text-xs font-medium text-muted-foreground">
                Job description
              </label>
              <textarea
                id="iv-jd"
                value={jdText}
                onChange={(e) => setJdText(e.target.value)}
                placeholder="Paste the job description here…"
                rows={8}
                className="field resize-y leading-6"
              />
            </div>

            {error && <Alert role="alert">{error}</Alert>}

            <Button type="submit" size="lg" disabled={!provider || !jdText.trim()} className="self-start">
              Start interview
            </Button>
          </form>
        </Card>
      )}
    </div>
  );
}
