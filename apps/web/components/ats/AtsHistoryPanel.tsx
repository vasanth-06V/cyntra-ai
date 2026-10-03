"use client";

import { useEffect, useRef, useState } from "react";
import { apiClient, ApiError } from "@/lib/api-client/fastapi";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useConfirm } from "@/components/ui/ConfirmProvider";
import { EmptyState } from "@/components/ui/EmptyState";
import { ListRow } from "@/components/ui/ListRow";
import { ListSkeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";
import { ClockIcon, RefreshIcon, TrashIcon } from "@/components/ui/icons";
import { scoreTone, toneText } from "@/components/ui/score";
import { ScoreRing } from "@/components/ui/ScoreRing";
import { relativeTime } from "@/lib/format";
import { ATS_HISTORY_KEPT, type AtsHistoryDetail, type AtsHistoryItem } from "@/types/ats";

function ScoreMini({ score }: { score: number }) {
  const tone = scoreTone(score / 100);
  return (
    <span className="relative inline-flex h-12 w-12 shrink-0 items-center justify-center" role="img" aria-label={`Score ${score} out of 100`}>
      <ScoreRing value={score} size={48} stroke={5} showValue={false} />
      <span className={`absolute text-sm font-semibold tabular-nums ${toneText[tone]}`}>{score}</span>
    </span>
  );
}

/**
 * "Previous checks" for one resume: the saved results the API keeps (the last
 * 10). Mount it with `key={resumeId}` so switching resumes starts clean.
 * `refreshKey` changes after every new score so the list refetches quietly.
 */
export function AtsHistoryPanel({
  resumeId,
  refreshKey,
  activeId,
  onOpen,
  onDeleted,
}: {
  resumeId: string;
  refreshKey: number;
  /** The saved check currently on screen, marked in the list. */
  activeId: string | null;
  onOpen: (detail: AtsHistoryDetail) => void;
  onDeleted: (id: string) => void;
}) {
  const confirm = useConfirm();
  const { toast } = useToast();
  const [items, setItems] = useState<AtsHistoryItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [openingId, setOpeningId] = useState<string | null>(null);
  const loadedOnce = useRef(false);

  useEffect(() => {
    let cancelled = false;
    apiClient
      .get<AtsHistoryItem[]>(`/ats/history?resume_id=${encodeURIComponent(resumeId)}&limit=${ATS_HISTORY_KEPT}`)
      .then((list) => {
        if (cancelled) return;
        loadedOnce.current = true;
        setItems(Array.isArray(list) ? list : []);
        setError(null);
      })
      .catch((err) => {
        // A quiet refresh that fails keeps the list we already have.
        if (cancelled || loadedOnce.current) return;
        setError(err instanceof ApiError ? err.message : "Could not load your previous checks.");
      });
    return () => {
      cancelled = true;
    };
  }, [resumeId, refreshKey, attempt]);

  async function open(item: AtsHistoryItem) {
    if (openingId) return;
    setOpeningId(item.id);
    try {
      onOpen(await apiClient.get<AtsHistoryDetail>(`/ats/history/${item.id}`));
    } catch (err) {
      toast({
        tone: "error",
        title: "Could not open this check",
        description: err instanceof ApiError ? err.message : "Please try again.",
      });
    } finally {
      setOpeningId(null);
    }
  }

  async function remove(item: AtsHistoryItem) {
    try {
      await apiClient.delete(`/ats/history/${item.id}`);
    } catch (err) {
      throw new Error(err instanceof ApiError ? err.message : "Could not delete this check.");
    }
    setItems((prev) => (prev ? prev.filter((x) => x.id !== item.id) : prev));
    onDeleted(item.id);
  }

  async function handleDelete(item: AtsHistoryItem) {
    const ok = await confirm({
      title: "Delete this saved check?",
      description: (
        <>
          <span className="font-medium text-foreground">{item.job_title || "Untitled role"}</span> (score{" "}
          {item.composite_score}, {relativeTime(item.created_at)}) will be removed. Your resume is not affected.
        </>
      ),
      confirmLabel: "Delete check",
      tone: "danger",
      onConfirm: () => remove(item),
    });
    if (ok) toast({ tone: "success", title: "Saved check deleted" });
  }

  return (
    <section aria-labelledby="ats-history-title" className="mt-8 max-w-2xl">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 id="ats-history-title" className="text-base font-semibold tracking-tight">
          Previous checks
        </h2>
        <p className="text-xs text-muted-foreground">The last {ATS_HISTORY_KEPT} checks per resume are kept.</p>
      </div>

      {items === null && !error ? (
        <ListSkeleton className="mt-3" rows={2} label="Loading previous checks…" />
      ) : error ? (
        <div className="mt-3 flex flex-col items-start gap-3">
          <Alert role="alert" className="w-full">
            {error}
          </Alert>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setError(null);
              setAttempt((n) => n + 1);
            }}
          >
            <RefreshIcon size={14} />
            Try again
          </Button>
        </div>
      ) : items && items.length === 0 ? (
        <EmptyState className="mt-3 py-8" icon={<ClockIcon size={18} />} title="No previous checks yet">
          Each time you check this resume, the result is saved here so you can compare later.
        </EmptyState>
      ) : (
        <ul className="mt-3 flex flex-col gap-2" aria-label="Previous checks for this resume">
            {items?.map((item) => {
              const title = item.job_title || "Untitled role";
              const active = item.id === activeId;
              return (
                <li key={item.id}>
                  <ListRow
                    leading={<ScoreMini score={item.composite_score} />}
                    title={
                      <button
                        type="button"
                        onClick={() => void open(item)}
                        aria-label={`Open saved check: ${title}, score ${item.composite_score}`}
                        aria-busy={openingId === item.id || undefined}
                        className="block max-w-full truncate rounded text-left after:absolute after:inset-0 after:rounded-xl after:content-['']"
                      >
                        {title}
                      </button>
                    }
                    meta={
                      <>
                        {relativeTime(item.created_at)}
                        {openingId === item.id ? " · opening…" : ""}
                      </>
                    }
                    badge={
                      <>
                        {active && <Badge tone="brand">Showing</Badge>}
                        {item.jd_excerpt && (
                          <span className="line-clamp-2 max-w-prose text-xs leading-5 text-muted-foreground">
                            {item.jd_excerpt}
                          </span>
                        )}
                      </>
                    }
                    actions={
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => void handleDelete(item)}
                        aria-label={`Delete saved check: ${title}`}
                        className="text-muted-foreground hover:bg-destructive-soft hover:text-destructive"
                      >
                        <TrashIcon size={14} />
                      </Button>
                    }
                    className={active ? "border-primary/40" : ""}
                  />
                </li>
              );
            })}
        </ul>
      )}
    </section>
  );
}
