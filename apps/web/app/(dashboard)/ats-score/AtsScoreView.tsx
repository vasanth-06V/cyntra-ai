"use client";

import { useEffect, useState } from "react";
import { apiClient, ApiError } from "@/lib/api-client/fastapi";
import { Button } from "@/components/ui/Button";
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
      <h1 className="text-2xl font-semibold">ATS Score</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        See how well a resume matches a job description.
      </p>

      {loading ? (
        <p className="mt-6 text-sm text-muted-foreground">Loading…</p>
      ) : resumes.length === 0 ? (
        <div className="mt-6 rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
          Upload and process a resume first, from the Resumes page.
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-3">
          <div className="flex gap-2">
            <select
              value={resumeId}
              onChange={(e) => setResumeId(e.target.value)}
              className="flex-1 rounded-lg border border-border bg-transparent px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
            >
              {resumes.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.file_key.split("/").pop()}
                </option>
              ))}
            </select>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value as ProviderName)}
              disabled={validProviders.length === 0}
              className="rounded-lg border border-border bg-transparent px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
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

          <textarea
            value={jdText}
            onChange={(e) => setJdText(e.target.value)}
            placeholder="Paste the job description here…"
            rows={8}
            className="rounded-lg border border-border bg-transparent px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
          />

          <Button
            type="submit"
            disabled={scoring || !provider || !jdText.trim()}
            className="self-start"
          >
            {scoring ? "Scoring…" : "Check score"}
          </Button>

          {error && <p className="text-sm text-destructive">{error}</p>}
        </form>
      )}

      {result && (
        <div className="mt-8 max-w-5xl">
          <ScoreBreakdown result={result} />
        </div>
      )}
    </div>
  );
}
