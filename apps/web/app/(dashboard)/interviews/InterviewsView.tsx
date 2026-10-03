"use client";

import { useEffect, useState } from "react";
import { apiClient, ApiError } from "@/lib/api-client/fastapi";
import { Alert } from "@/components/ui/Alert";
import { Badge, type Tone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useConfirm } from "@/components/ui/ConfirmProvider";
import { useToast } from "@/components/ui/Toast";
import { LinkButton } from "@/components/ui/LinkButton";
import { ListRow } from "@/components/ui/ListRow";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { ListSkeleton } from "@/components/ui/Skeleton";
import { MicIcon, PlusIcon, RefreshIcon, TrashIcon } from "@/components/ui/icons";
import { INTERVIEW_TYPE_LABELS, type Interview, type InterviewStatus } from "@/types/interviews";

const STATUS_TONE: Record<InterviewStatus, Tone> = {
  setting_up: "info",
  in_progress: "brand",
  completed: "success",
  aborted: "neutral",
};

const PAGE_SIZE = 50;

export function InterviewsView() {
  const confirm = useConfirm();
  const { toast } = useToast();
  const [interviews, setInterviews] = useState<Interview[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);

  useEffect(() => {
    apiClient
      .get<Interview[]>("/interviews")
      .then((list) => {
        setInterviews(list);
        setHasMore(list.length >= PAGE_SIZE);
        setError(null);
      })
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Could not load interviews.")
      )
      .finally(() => setLoading(false));
  }, [attempt]);

  // The API returns the newest 50 at a time; older ones are fetched on request.
  async function loadMore() {
    setLoadingMore(true);
    try {
      const next = await apiClient.get<Interview[]>(`/interviews?limit=${PAGE_SIZE}&offset=${interviews.length}`);
      setInterviews((prev) => [...prev, ...next.filter((n) => !prev.some((p) => p.id === n.id))]);
      setHasMore(next.length >= PAGE_SIZE);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load older interviews.");
    } finally {
      setLoadingMore(false);
    }
  }

  async function deleteInterview(iv: Interview) {
    try {
      await apiClient.delete(`/interviews/${iv.id}`);
    } catch (err) {
      throw new Error(err instanceof ApiError ? err.message : "Could not delete this interview.");
    }
    setInterviews((prev) => prev.filter((x) => x.id !== iv.id));
  }

  async function handleDelete(iv: Interview) {
    const label = INTERVIEW_TYPE_LABELS[iv.type] ?? iv.type;
    const when = new Date(iv.created_at).toLocaleString();
    const ok = await confirm({
      title: "Delete this interview?",
      description: (
        <>
          <span className="font-medium text-foreground">
            {label}, {when}
          </span>
          : the transcript, any submitted code and the report are removed too. This can&apos;t be undone.
        </>
      ),
      confirmLabel: "Delete interview",
      tone: "danger",
      onConfirm: () => deleteInterview(iv),
    });
    if (ok) toast({ tone: "success", title: "Interview deleted" });
  }

  return (
    <div>
      <PageHeader
        title="Interviews"
        description="Timed mock interviews built from your resume and a job description."
        actions={
          <LinkButton href="/interviews/setup">
            <PlusIcon size={16} />
            Start new interview
          </LinkButton>
        }
      />

      {loading ? (
        <ListSkeleton className="mt-6" rows={4} />
      ) : error ? (
        <div className="mt-6 flex flex-col items-start gap-3">
          <Alert role="alert" className="w-full">
            {error}
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
      ) : interviews.length === 0 ? (
        <EmptyState
          className="mt-6"
          icon={<MicIcon size={20} />}
          title="No interviews yet"
          action={<LinkButton href="/interviews/setup" variant="outline" size="sm">Set up your first interview</LinkButton>}
        >
          A mock interview takes about an hour and is built from your resume and a job description.
        </EmptyState>
      ) : (
        <ul className="stagger mt-6 flex max-w-3xl flex-col gap-2" aria-label="Your interviews">
          {interviews.map((iv) => (
            <li key={iv.id}>
              <ListRow
                href={`/interviews/${iv.id}`}
                icon={<MicIcon size={18} />}
                title={INTERVIEW_TYPE_LABELS[iv.type] ?? iv.type}
                meta={new Date(iv.created_at).toLocaleString()}
                trailing={
                  <Badge tone={STATUS_TONE[iv.status] ?? "neutral"} className="capitalize">
                    {iv.status.replace(/_/g, " ")}
                  </Badge>
                }
                actions={
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => void handleDelete(iv)}
                    aria-label={`Delete ${INTERVIEW_TYPE_LABELS[iv.type] ?? iv.type} interview from ${new Date(iv.created_at).toLocaleString()}`}
                    className="text-muted-foreground hover:bg-destructive-soft hover:text-destructive"
                  >
                    <TrashIcon size={14} />
                  </Button>
                }
              />
            </li>
          ))}
        </ul>
      )}
      {hasMore && !loading && !error && (
        <Button variant="outline" className="mt-4" onClick={() => void loadMore()} loading={loadingMore}>
          Show older interviews
        </Button>
      )}
    </div>
  );
}
