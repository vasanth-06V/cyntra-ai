"use client";

import { useEffect, useState } from "react";
import { apiClient, ApiError } from "@/lib/api-client/fastapi";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { FormSkeleton } from "@/components/ui/Skeleton";
import { FileIcon } from "@/components/ui/icons";
import { ScoreBreakdown } from "@/components/ats/ScoreBreakdown";
import type { ScoreResponse } from "@/types/ats";
import { PROVIDER_INFO, type ProviderKey, type ProviderName } from "@/types/keys";
import type { Resume } from "@/types/resumes";

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
          .filter((k) => k.slot === "primary" && k.is_valid)
          .map((k) => k.provider);
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
                      {r.file_key.split("/").pop()}
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
                  value={provider}
                  onChange={(e) => setProvider(e.target.value as ProviderName)}
                  disabled={validProviders.length === 0}
                  className="field"
                >
                  {validProviders.length === 0 ? (
                    <option>No valid keys</option>
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
                placeholder="Paste the job description here…"
                rows={8}
                className="field resize-y leading-6"
              />
            </div>

            <Button
              type="submit"
              loading={scoring}
              disabled={!provider || !jdText.trim()}
              className="self-start"
            >
              {scoring ? "Scoring…" : "Check score"}
            </Button>

            {error && <Alert role="alert">{error}</Alert>}
          </form>
        </Card>
      )}

      {result && (
        <div className="mt-8 max-w-5xl">
          <ScoreBreakdown result={result} />
        </div>
      )}
    </div>
  );
}
