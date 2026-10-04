"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { apiClient, ApiError } from "@/lib/api-client/fastapi";
import { useTheme } from "next-themes";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { CodeIcon } from "@/components/ui/icons";
import type { Job } from "@/types/jobs";
import type { ProblemState, SubmissionStarted } from "@/types/coding";

type EditorProps = {
  value: string;
  onChange: (value: string | undefined) => void;
  language: string;
  dark: boolean;
  readOnly: boolean;
};

const EDITOR_LOAD_TIMEOUT_MS = 25_000;

/** Used when Monaco cannot be loaded (its files come from a CDN): typing and submitting still work. */
function EditorFallback({ value, onChange, readOnly }: EditorProps) {
  return (
    <div className="flex h-full flex-col gap-2 p-3">
      <p role="status" className="text-xs text-muted-foreground">
        Editor failed to load - reload the page to get syntax highlighting. You can still type your solution here.
      </p>
      <textarea
        aria-label="Solution code"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        readOnly={readOnly}
        spellCheck={false}
        className="field min-h-[220px] flex-1 resize-none font-mono text-[13px]"
      />
    </div>
  );
}

// Monaco is large: load it only when a coding problem is actually active. A
// failed or hanging load (blocked CDN, offline) falls back to a plain textarea.
const Editor = dynamic<EditorProps>(
  async () => {
    try {
      const monaco = await Promise.race([
        import("@monaco-editor/react").then(async (m) => {
          await m.loader.init();
          return m;
        }),
        new Promise<never>((_, reject) =>
          setTimeout(() => reject(new Error("editor load timeout")), EDITOR_LOAD_TIMEOUT_MS)
        ),
      ]);
      const Monaco = monaco.default;
      return function MonacoEditor({ value, onChange, language, dark, readOnly }: EditorProps) {
        return (
          <Monaco
            height="100%"
            language={language}
            value={value}
            onChange={onChange}
            theme={dark ? "vs-dark" : "light"}
            options={{
              readOnly,
              minimap: { enabled: false },
              fontSize: 14,
              scrollBeyondLastLine: false,
              automaticLayout: true,
              tabSize: 4,
              ariaLabel: "Solution code",
            }}
          />
        );
      };
    } catch {
      return EditorFallback;
    }
  },
  {
    ssr: false,
    loading: () => (
      <div role="status" className="flex h-full min-h-[260px] flex-col gap-2 p-4">
        <span className="sr-only">Loading editor…</span>
        <Skeleton className="h-4 w-1/3" />
        <Skeleton className="h-4 w-2/3" />
        <Skeleton className="h-4 w-1/2" />
        <Skeleton className="h-4 w-3/5" />
      </div>
    ),
  }
);

// Any language is accepted; these get syntax highlighting and a menu entry.
const LANGUAGES: { label: string; monaco: string }[] = [
  { label: "Python", monaco: "python" },
  { label: "JavaScript", monaco: "javascript" },
  { label: "TypeScript", monaco: "typescript" },
  { label: "Java", monaco: "java" },
  { label: "C++", monaco: "cpp" },
  { label: "C", monaco: "c" },
  { label: "C#", monaco: "csharp" },
  { label: "Go", monaco: "go" },
  { label: "Rust", monaco: "rust" },
  { label: "Ruby", monaco: "ruby" },
  { label: "Kotlin", monaco: "kotlin" },
  { label: "Swift", monaco: "swift" },
  { label: "PHP", monaco: "php" },
  { label: "SQL", monaco: "sql" },
];
const OTHER = "Other…";

const POLL_EVERY_MS = 1500;
const GIVE_UP_AFTER_MS = 5 * 60 * 1000; // matches the backend worst case for a code review
const PHASE_REFRESH_MS = 20_000;
const MAX_CODE = 8000;

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

function draftKey(interviewId: string, problem: number | null | undefined) {
  return `cyntra:draft:${interviewId}:${problem ?? 0}`;
}

function readDraft(key: string): { code: string; language: string } | null {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as { code: string; language: string }) : null;
  } catch {
    return null;
  }
}

function writeDraft(key: string, value: { code: string; language: string }) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // storage unavailable: the draft just isn't remembered
  }
}

type Props = {
  interviewId: string;
  /** Changes whenever the interview moves on (a turn arrived), to re-check the phase. */
  refreshKey: string;
  /** Tells the room a review is running (it pauses the chat) and when it ends. */
  onBusyChange: (busy: boolean) => void;
  /** The review finished: reload the transcript, which now holds the interviewer's reaction. */
  onReviewed: () => void;
  onProblemChange: (active: boolean) => void;
};

export function CodeEditorPanel({
  interviewId,
  refreshKey,
  onBusyChange,
  onReviewed,
  onProblemChange,
}: Props) {
  const { resolvedTheme } = useTheme();
  const [problem, setProblem] = useState<ProblemState | null>(null);
  const [code, setCode] = useState("");
  const [languageChoice, setLanguageChoice] = useState("Python");
  const [customLanguage, setCustomLanguage] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [progress, setProgress] = useState<string | null>(null);
  const [reviewing, setReviewing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(true);
  const loadedKey = useRef<string | null>(null);
  const polling = useRef(false); // one review poll at a time

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const language = languageChoice === OTHER ? customLanguage.trim() : languageChoice;
  const monacoLanguage = LANGUAGES.find((l) => l.label === language)?.monaco ?? "plaintext";

  const refresh = useCallback(async () => {
    try {
      const state = await apiClient.get<ProblemState>(`/interviews/${interviewId}/problem`);
      if (!mounted.current) return;
      setProblem(state);
      onProblemChange(state.enabled && state.active);
    } catch {
      // a missed refresh is harmless: the next one catches up
    }
  }, [interviewId, onProblemChange]);

  useEffect(() => {
    const t = setTimeout(() => void refresh(), 0);
    return () => clearTimeout(t);
  }, [refresh, refreshKey]);

  // Phases change with the clock, not only with turns.
  useEffect(() => {
    const id = setInterval(() => void refresh(), PHASE_REFRESH_MS);
    return () => clearInterval(id);
  }, [refresh]);

  // Restore the unsent draft for this problem once.
  const key = problem?.active ? draftKey(interviewId, problem.problem_number) : null;
  useEffect(() => {
    if (!key || loadedKey.current === key) return;
    loadedKey.current = key;
    const draft = readDraft(key);
    queueMicrotask(() => {
      if (!mounted.current) return;
      setCode(draft?.code ?? "");
      if (draft?.language) {
        const known = LANGUAGES.some((l) => l.label === draft.language);
        setLanguageChoice(known ? draft.language : OTHER);
        if (!known) setCustomLanguage(draft.language);
      }
    });
  }, [key]);

  function onCodeChange(value: string | undefined) {
    const next = value ?? "";
    setCode(next);
    if (key) writeDraft(key, { code: next, language });
  }

  const pollReview = useCallback(
    async (jobId: string) => {
      if (polling.current) return;
      polling.current = true;
      setReviewing(true);
      onBusyChange(true);
      setError(null);
      try {
        const deadline = Date.now() + GIVE_UP_AFTER_MS;
        while (mounted.current) {
          const job = await apiClient.get<Job>(`/jobs/${jobId}`);
          if (job.status === "succeeded") {
            onReviewed();
            return;
          }
          if (job.status === "failed") {
            throw new ApiError(
              job.error?.status ?? 500,
              job.error?.message ?? "Could not review your solution.",
              job.error?.code
            );
          }
          if (Date.now() > deadline) {
            throw new ApiError(504, "The review is taking longer than expected -- please refresh.");
          }
          setProgress(job.status === "queued" ? "Waiting for a free slot..." : job.progress);
          await sleep(POLL_EVERY_MS);
        }
      } catch (err) {
        if (mounted.current) {
          setError(err instanceof ApiError ? err.message : "Could not review your solution.");
        }
      } finally {
        polling.current = false;
        if (mounted.current) {
          setReviewing(false);
          setProgress(null);
          onBusyChange(false);
          await refresh();
        }
      }
    },
    [onBusyChange, onReviewed, refresh]
  );

  // A review that was running when the page was reloaded: pick it back up.
  useEffect(() => {
    const jobId = problem?.review_job_id;
    if (!jobId || reviewing) return;
    const t = setTimeout(() => void pollReview(jobId), 0);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [problem?.review_job_id]);

  async function handleSubmit() {
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const started = await apiClient.post<SubmissionStarted>(
        `/interviews/${interviewId}/submissions`,
        { language, code }
      );
      setConfirming(false);
      setSubmitting(false);
      await pollReview(started.job_id);
    } catch (err) {
      setConfirming(false);
      setSubmitting(false);
      setError(err instanceof ApiError ? err.message : "Could not submit your solution.");
      await refresh();
    }
  }

  if (!problem?.enabled || !problem.active) return null;

  const submission = problem.submission;
  const locked = Boolean(submission) || reviewing;
  const canSubmit = !locked && code.trim().length > 0 && language.length > 0 && code.length <= MAX_CODE;

  return (
    <section
      aria-label="Code editor"
      className="flex min-h-0 animate-slide-in flex-col border-t border-border bg-card max-lg:min-h-[30rem] lg:border-l lg:border-t-0"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-background/60 px-3 py-2">
        <p className="flex items-center gap-2 text-sm font-semibold">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent text-accent-foreground">
            <CodeIcon size={15} />
          </span>
          Problem {problem.problem_number} of {problem.total_problems}
        </p>
        <div className="flex items-center gap-2">
          <label className="sr-only" htmlFor="language">
            Language
          </label>
          <select
            id="language"
            value={submission ? (LANGUAGES.some((l) => l.label === submission.language) ? submission.language : OTHER) : languageChoice}
            onChange={(e) => setLanguageChoice(e.target.value)}
            disabled={locked}
            className="field field-sm"
          >
            {LANGUAGES.map((l) => (
              <option key={l.label} value={l.label}>
                {l.label}
              </option>
            ))}
            <option value={OTHER}>{OTHER}</option>
          </select>
          {languageChoice === OTHER && !submission && (
            <input
              value={customLanguage}
              onChange={(e) => setCustomLanguage(e.target.value)}
              placeholder="Language name"
              aria-label="Language name"
              maxLength={30}
              disabled={locked}
              className="field field-sm w-32"
            />
          )}
        </div>
      </div>

      {problem.question && (
        <div className="max-h-36 overflow-y-auto border-b border-border bg-accent/40 px-4 py-3 text-sm leading-6">
          {problem.question}
        </div>
      )}

      <div className="min-h-[260px] flex-1">
        <Editor
          value={code}
          onChange={onCodeChange}
          language={monacoLanguage}
          dark={resolvedTheme === "dark"}
          readOnly={locked}
        />
      </div>

      <div className="border-t border-border bg-background/60 p-3">
        {submission ? (
          <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
            <Badge tone={submission.status === "review" || reviewing ? "info" : "success"}>
              {submission.status === "review" || reviewing ? "Reviewing" : "Submitted"}
            </Badge>
            {submission.status === "review" || reviewing
              ? (progress ?? "Reviewing your solution…")
              : `Submitted · ${submission.language} · ${submission.line_count} lines. Keep talking it through with the interviewer.`}
          </p>
        ) : confirming ? (
          <div role="group" aria-label="Confirm submission" className="flex flex-wrap items-center gap-2">
            <p className="text-sm">
              Submit this {language} solution? You can submit only once for this problem.
            </p>
            <Button type="button" onClick={handleSubmit} loading={submitting}>
              {submitting ? "Submitting…" : "Yes, submit"}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => setConfirming(false)}
              disabled={submitting}
              autoFocus
            >
              Keep editing
            </Button>
          </div>
        ) : (
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs text-muted-foreground">
              Nothing is run. Your code goes to the interviewer, who reviews the logic.
            </p>
            <Button type="button" onClick={() => setConfirming(true)} disabled={!canSubmit}>
              Submit solution
            </Button>
          </div>
        )}
        {code.length > MAX_CODE && (
          <Alert role="alert" className="mt-2">
            Too long to review ({code.length}/{MAX_CODE} characters).
          </Alert>
        )}
        {error && (
          <Alert role="alert" className="mt-2">
            {error}
          </Alert>
        )}
      </div>
    </section>
  );
}
