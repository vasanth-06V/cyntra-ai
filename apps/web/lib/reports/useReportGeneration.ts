"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiClient, ApiError } from "@/lib/api-client/fastapi";
import type { Job } from "@/types/jobs";

const POLL_EVERY_MS = 1500;
const GIVE_UP_AFTER_MS = 6 * 60 * 1000; // matches the backend worst case
const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

type Started = { ready: boolean; job_id: string | null };

/** Starts a report for an interview and waits for it, reporting progress. */
export function useReportGeneration(onReady: (interviewId: string) => void) {
  const [busyId, setBusyId] = useState<string | null>(null);
  const [progress, setProgress] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const start = useCallback(
    async (interviewId: string) => {
      setBusyId(interviewId);
      setProgress("Starting…");
      setError(null);
      try {
        const started = await apiClient.post<Started>(`/interviews/${interviewId}/report`);
        if (!started.ready && started.job_id) {
          const deadline = Date.now() + GIVE_UP_AFTER_MS;
          while (mounted.current) {
            const job = await apiClient.get<Job>(`/jobs/${started.job_id}`);
            if (job.status === "succeeded") break;
            if (job.status === "failed") {
              throw new ApiError(
                job.error?.status ?? 500,
                job.error?.message ?? "Could not write the report.",
                job.error?.code
              );
            }
            if (Date.now() > deadline) {
              throw new ApiError(504, "The report is taking longer than expected -- please try again.");
            }
            setProgress(job.status === "queued" ? "Waiting for a free slot…" : job.progress);
            await sleep(POLL_EVERY_MS);
          }
        }
        if (mounted.current) onReady(interviewId);
      } catch (err) {
        if (mounted.current) {
          setError(err instanceof ApiError ? err.message : "Could not write the report.");
        }
      } finally {
        if (mounted.current) {
          setBusyId(null);
          setProgress(null);
        }
      }
    },
    [onReady]
  );

  return { busyId, progress, error, start };
}
