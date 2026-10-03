"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { apiClient, ApiError } from "@/lib/api-client/fastapi";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { FormSkeleton } from "@/components/ui/Skeleton";
import { FileIcon, KeyIcon, RefreshIcon } from "@/components/ui/icons";
import { LinkButton } from "@/components/ui/LinkButton";
import { fetchResumes, resumeName } from "@/lib/resumes";
import { ScoreBreakdown } from "@/components/ats/ScoreBreakdown";
import type { ScoreResponse } from "@/types/ats";
import { PROVIDER_INFO, type ProviderKey, type ProviderName } from "@/types/keys";
import type { Resume } from "@/types/resumes";

const JD_MIN = 10;
const JD_MAX = 20000;

export function AtsScoreView() {
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [validProviders, setValidProviders] = useState<ProviderName[]>([]);
  const [resumeId, setResumeId] = useState("");
  const [provider, setProvider] = useState<ProviderName | undefined>();
  const [jdText, setJdText] = useState("");
  const [loading, setLoading] = useState(true);
  const [scoring, setScoring] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ScoreResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const resultRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    Promise.all([fetchResumes(), apiClient.get<ProviderKey[]>("/keys")])
      .then(([resumeData, keys]: [Resume[], ProviderKey[]]) => {
        setLoadError(null);
        const processed = resumeData.filter((r) => r.parsed_text);
        setResumes(processed);
        if (processed[0]) setResumeId(processed[0].id);

        const providers = keys
          .filter((k) => k.slot === "primary" && k.is_valid)
          .map((k) => k.provider);
        setValidProviders(providers);
        setProvider(providers[0]);
      })
      .catch((err) =>
        setLoadError(err instanceof Error ? err.message : "Could not load resumes or keys.")
      )
      .finally(() => setLoading(false));
  }, [attempt]);

  const jdLength = jdText.trim().length;
  const jdTooShort = jdLength > 0 && jdLength < JD_MIN;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!resumeId || !provider || jdLength < JD_MIN || jdText.length > JD_MAX) return;

    setScoring(true);
    setError(null);
    setResult(null);

    try {
      const response = await apiClient.post<ScoreResponse>("/ats/score", {
        resume_id: resumeId,
        jd_text: jdText,
        provider,
      });
      setResult(response);
      // Bring the result into view and let screen readers find it.
      setTimeout(() => {
        resultRef.current?.scrollIntoView?.({ block: "start", behavior: "smooth" });
        resultRef.current?.focus({ preventScroll: true });
      }, 50);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Scoring failed.");
    } finally {
      setScoring(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="ATS Score"
        description="See how well a resume matches a job description."
      />

      {loading ? (
        <FormSkeleton className="mt-6 max-w-2xl" />
      ) : loadError ? (
        <div className="mt-6 flex max-w-2xl flex-col items-start gap-3">
          <Alert role="alert" className="w-full">
            {loadError}
          </Alert>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setLoading(true);
              setAttempt((n) => n + 1);
            }}
          >
            <RefreshIcon size={14} />
            Try again
          </Button>
        </div>
      ) : resumes.length === 0 ? (
        <EmptyState
          className="mt-6"
          icon={<FileIcon size={20} />}
          title="No processed resume yet"
          action={
            <LinkButton href="/resumes" variant="outline" size="sm">
              Go to Resumes
            </LinkButton>
          }
        >
          Upload a resume and let it finish processing, then come back to score it against a job description.
        </EmptyState>
      ) : (
        <Card className="mt-6 max-w-2xl p-5 sm:p-6">
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-4 sm:flex-row">
              <div className="flex min-w-0 flex-1 flex-col gap-1.5">
                <label htmlFor="ats-resume" className="text-xs font-medium text-muted-foreground">
                  Resume
                </label>
                <select
                  id="ats-resume"
                  value={resumeId}
                  onChange={(e) => setResumeId(e.target.value)}
                  className="field"
                >
                  {resumes.map((r) => (
                    <option key={r.id} value={r.id}>
                      {resumeName(r)}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex flex-col gap-1.5 sm:w-44">
                <label htmlFor="ats-provider" className="text-xs font-medium text-muted-foreground">
                  Model
                </label>
                <select
                  id="ats-provider"
                  value={provider ?? ""}
                  onChange={(e) => setProvider(e.target.value as ProviderName)}
                  disabled={validProviders.length === 0}
                  className="field"
                >
                  {validProviders.length === 0 ? (
                    <option value="">No valid keys</option>
                  ) : (
                    validProviders.map((p) => (
                      <option key={p} value={p}>
                        {PROVIDER_INFO[p].label}
                      </option>
                    ))
                  )}
                </select>
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor="ats-jd" className="text-xs font-medium text-muted-foreground">
                Job description
              </label>
              <textarea
                id="ats-jd"
                value={jdText}
                onChange={(e) => setJdText(e.target.value)}
                onKeyDown={(e) => {
                  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
                    e.preventDefault();
                    e.currentTarget.form?.requestSubmit();
                  }
                }}
                placeholder="Paste the job description here…"
                rows={8}
                maxLength={JD_MAX}
                aria-invalid={jdTooShort || undefined}
                aria-describedby="ats-jd-hint"
                className="field resize-y leading-6"
              />
              <p
                id="ats-jd-hint"
                className={`flex justify-between gap-3 text-xs ${jdTooShort ? "text-destructive" : "text-muted-foreground"}`}
              >
                <span>
                  {jdTooShort
                    ? `Add a little more: at least ${JD_MIN} characters.`
                    : "Ctrl+Enter to check the score."}
                </span>
                <span className="tabular-nums">
                  {jdText.length.toLocaleString()} / {JD_MAX.toLocaleString()}
                </span>
              </p>
            </div>

            {validProviders.length === 0 && (
              <Alert tone="warning">
                <span className="flex flex-wrap items-center gap-x-1.5">
                  <KeyIcon size={14} className="shrink-0" />
                  No working API key yet.
                  <Link href="/settings/api-keys" className="font-medium underline underline-offset-4">
                    Add one in API Keys
                  </Link>
                  to run a check.
                </span>
              </Alert>
            )}

            <Button
              type="submit"
              loading={scoring}
              disabled={!provider || jdLength < JD_MIN}
              className="self-start"
            >
              {scoring ? "Scoring…" : "Check score"}
            </Button>

            {error && <Alert role="alert">{error}</Alert>}
          </form>
        </Card>
      )}

      {result && (
        <div ref={resultRef} tabIndex={-1} role="region" aria-label="ATS score result" className="mt-8 max-w-5xl outline-none">
          <ScoreBreakdown result={result} />
        </div>
      )}
    </div>
  );
}
