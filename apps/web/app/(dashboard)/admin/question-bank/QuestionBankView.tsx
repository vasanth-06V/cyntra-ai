"use client";

import { useEffect, useRef, useState } from "react";
import { apiClient, ApiError } from "@/lib/api-client/fastapi";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { useConfirm } from "@/components/ui/ConfirmProvider";
import { useToast } from "@/components/ui/Toast";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { ListSkeleton } from "@/components/ui/Skeleton";
import { BookIcon, PencilIcon, RefreshIcon, TrashIcon } from "@/components/ui/icons";
import {
  INTERVIEW_TYPE_LABELS,
  type InterviewType,
  type Question,
} from "@/types/interviews";

const CODING_TYPES: InterviewType[] = ["coding", "webd", "sde"];

const INTERVIEW_TYPES = Object.keys(INTERVIEW_TYPE_LABELS) as InterviewType[];

export function QuestionBankView() {
  const confirm = useConfirm();
  const { toast } = useToast();
  const questionRef = useRef<HTMLTextAreaElement>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [filterType, setFilterType] = useState<InterviewType | "all">("all");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [type, setType] = useState<InterviewType>("coding");
  const [questionText, setQuestionText] = useState("");
  const [tagsText, setTagsText] = useState("");
  const [topicText, setTopicText] = useState("");
  const [difficulty, setDifficulty] = useState<string>("");
  const [solutionCode, setSolutionCode] = useState("");
  const [solutionLanguage, setSolutionLanguage] = useState("");
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // `loading` starts true, so the first load shows the spinner; later reloads
  // refresh the list in place instead of flashing it away.
  async function load() {
    try {
      setQuestions(await apiClient.get<Question[]>("/interviews/question-bank"));
      setLoadError(null);
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.message : "Could not load the question bank.");
    } finally {
      setLoading(false);
    }
  }

  // Initial load is written out inline: calling load() from an effect makes
  // React treat its state updates as synchronous in the effect body.
  useEffect(() => {
    apiClient
      .get<Question[]>("/interviews/question-bank")
      .then(setQuestions)
      .catch((err) =>
        setLoadError(err instanceof ApiError ? err.message : "Could not load the question bank.")
      )
      .finally(() => setLoading(false));
  }, []);

  function resetForm() {
    setEditingId(null);
    setQuestionText("");
    setTagsText("");
    setTopicText("");
    setDifficulty("");
    setSolutionCode("");
    setSolutionLanguage("");
    setFormError(null);
  }

  function startEdit(q: Question) {
    setEditingId(q.id);
    setType(q.type);
    setQuestionText(q.question);
    setTagsText((q.tags ?? []).join(", "));
    setTopicText(q.topic ?? "");
    setDifficulty(q.difficulty ? String(q.difficulty) : "");
    setSolutionCode(q.solution_code ?? "");
    setSolutionLanguage(q.solution_language ?? "");
    setFormError(null);
    // The form sits above a long list: bring it into view and put the cursor in it.
    questionRef.current?.scrollIntoView?.({ block: "center" });
    questionRef.current?.focus({ preventScroll: true });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);

    const needsSolution = CODING_TYPES.includes(type);
    if (needsSolution && !solutionCode.trim()) {
      setFormError("Coding questions need a reference solution (the interviewer judges against it).");
      return;
    }

    const tags = tagsText
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);

    setSaving(true);
    try {
      if (editingId) {
        await apiClient.patch(`/interviews/question-bank/${editingId}`, {
          question: questionText,
          solution_code: solutionCode,
          solution_language: solutionLanguage.trim(),
          tags,
          // On an edit an explicit null clears the field (omitting it would leave it unchanged).
          topic: topicText.trim() || null,
          difficulty: difficulty ? Number(difficulty) : null,
        });
      } else {
        await apiClient.post("/interviews/question-bank", {
          type,
          question: questionText,
          solution_code: solutionCode || undefined,
          solution_language: solutionLanguage.trim() || undefined,
          tags,
          topic: topicText.trim() || undefined,
          difficulty: difficulty ? Number(difficulty) : undefined,
        });
      }
      const wasEditing = Boolean(editingId);
      resetForm();
      toast({ tone: "success", title: wasEditing ? "Question updated" : "Question added" });
      await load();
    } catch (err) {
      setFormError(
        err instanceof ApiError ? err.message : "Could not save this question."
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(q: Question) {
    const preview = q.question.length > 90 ? `${q.question.slice(0, 90)}…` : q.question;
    const ok = await confirm({
      title: "Delete this question?",
      description: (
        <>
          It will be removed from the bank and no longer used to build interviews:{" "}
          <span className="text-foreground">&ldquo;{preview}&rdquo;</span>
        </>
      ),
      confirmLabel: "Delete question",
      tone: "danger",
      onConfirm: async () => {
        try {
          await apiClient.delete(`/interviews/question-bank/${q.id}`);
        } catch (err) {
          throw new Error(err instanceof ApiError ? err.message : "Could not delete this question.");
        }
        setQuestions((prev) => prev.filter((x) => x.id !== q.id));
      },
    });
    if (ok) {
      if (editingId === q.id) resetForm();
      toast({ tone: "success", title: "Question deleted" });
    }
  }

  const visibleQuestions =
    filterType === "all" ? questions : questions.filter((q) => q.type === filterType);

  return (
    <div>
      <PageHeader
        title="Question Bank"
        description="Manage interview questions and test cases. Saving requires a valid Gemini key (each question is embedded for RAG selection)."
      />

      <Card className="mt-6 max-w-3xl p-5 sm:p-6">
        <h2 className="text-sm font-semibold">
          {editingId ? "Edit question" : "Add a question"}
        </h2>
        <form onSubmit={handleSubmit} className="mt-3 flex flex-col gap-3">
          <select
            value={type}
            aria-label="Question type"
            onChange={(e) => setType(e.target.value as InterviewType)}
            disabled={!!editingId}
            className="field"
          >
            {INTERVIEW_TYPES.map((t) => (
              <option key={t} value={t}>
                {INTERVIEW_TYPE_LABELS[t]}
              </option>
            ))}
          </select>

          <textarea
            ref={questionRef}
            value={questionText}
            onChange={(e) => setQuestionText(e.target.value)}
            onKeyDown={(e) => {
              if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
                e.preventDefault();
                e.currentTarget.form?.requestSubmit();
              }
            }}
            placeholder="Question text… (Ctrl+Enter to save)"
            aria-label="Question text"
            rows={3}
            maxLength={4000}
            required
            className="field"
          />

          <input
            aria-label="Tags"
            value={tagsText}
            onChange={(e) => setTagsText(e.target.value)}
            placeholder="Tags, comma separated (optional)"
            className="field"
          />

          <div className="flex flex-wrap gap-3 sm:flex-nowrap">
            <input
              value={topicText}
              onChange={(e) => setTopicText(e.target.value)}
              placeholder="Topic, e.g. arrays, caching, conflict (optional)"
              aria-label="Topic"
              maxLength={60}
              className="field min-w-0 flex-1"
            />
            <select
              value={difficulty}
              onChange={(e) => setDifficulty(e.target.value)}
              aria-label="Difficulty"
              className="field"
            >
              <option value="">Difficulty</option>
              {[1, 2, 3, 4, 5].map((d) => (
                <option key={d} value={d}>
                  {d} {d === 1 ? "(easy)" : d === 5 ? "(hard)" : ""}
                </option>
              ))}
            </select>
          </div>

          {CODING_TYPES.includes(type) && (
            <div className="flex flex-col gap-2">
              <label className="text-xs text-muted-foreground" htmlFor="solution-code">
                Reference solution (required for coding questions). The interviewer compares each
                candidate&apos;s submission against it; candidates never see it.
              </label>
              <textarea
                id="solution-code"
                value={solutionCode}
                onChange={(e) => setSolutionCode(e.target.value)}
                placeholder="Paste a correct, ideally optimal, solution…"
                rows={8}
                maxLength={8000}
                spellCheck={false}
                className="field font-mono text-xs"
              />
              <input
                value={solutionLanguage}
                onChange={(e) => setSolutionLanguage(e.target.value)}
                placeholder="Language of the solution, e.g. Python"
                aria-label="Solution language"
                maxLength={30}
                className="field"
              />
            </div>
          )}

          {editingId && (
            <p className="text-xs text-muted-foreground">
              Leave the topic empty or the difficulty blank to clear them.
            </p>
          )}

          {formError && <Alert role="alert">{formError}</Alert>}

          <div className="flex gap-2">
            <Button type="submit" loading={saving} disabled={!questionText.trim()}>
              {saving ? "Saving…" : editingId ? "Save changes" : "Add question"}
            </Button>
            {editingId && (
              <Button type="button" variant="outline" onClick={resetForm}>
                Cancel
              </Button>
            )}
          </div>
        </form>
      </Card>

      <div className="mt-8 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-muted-foreground">
          {visibleQuestions.length} question{visibleQuestions.length === 1 ? "" : "s"}
        </h2>
        <select
          value={filterType}
          aria-label="Filter by type"
          onChange={(e) => setFilterType(e.target.value as InterviewType | "all")}
          className="field field-sm"
        >
          <option value="all">All types</option>
          {INTERVIEW_TYPES.map((t) => (
            <option key={t} value={t}>
              {INTERVIEW_TYPE_LABELS[t]}
            </option>
          ))}
        </select>
      </div>

      {loading ? (
        <ListSkeleton className="mt-4" rows={3} />
      ) : loadError ? (
        <div className="mt-4 flex flex-col items-start gap-3">
          <Alert role="alert" className="w-full">
            {loadError}
          </Alert>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setLoading(true);
              void load();
            }}
          >
            <RefreshIcon size={14} />
            Try again
          </Button>
        </div>
      ) : visibleQuestions.length === 0 ? (
        <EmptyState className="mt-4" icon={<BookIcon size={20} />} title="No questions yet">
          No questions yet.
        </EmptyState>
      ) : (
        <div className="stagger mt-4 flex flex-col gap-2">
          {visibleQuestions.map((q) => (
            <Card key={q.id} className="p-4">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <Badge tone="brand">{INTERVIEW_TYPE_LABELS[q.type]}</Badge>
                  <p className="mt-1.5 text-sm leading-6">{q.question}</p>
                  {(q.topic || q.difficulty) && (
                    <p className="mt-1 text-xs text-muted-foreground">
                      {[q.topic, q.difficulty ? `difficulty ${q.difficulty}/5` : null]
                        .filter(Boolean)
                        .join(" · ")}
                    </p>
                  )}
                  {q.tags && q.tags.length > 0 && (
                    <p className="mt-1 text-xs text-muted-foreground">
                      {q.tags.join(", ")}
                    </p>
                  )}
                </div>
                <div className="flex shrink-0 gap-1">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => startEdit(q)}
                    aria-label={`Edit question: ${q.question.slice(0, 40)}`}
                  >
                    <PencilIcon size={14} />
                    Edit
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDelete(q)}
                    aria-label={`Delete question: ${q.question.slice(0, 40)}`}
                    className="text-muted-foreground hover:bg-destructive-soft hover:text-destructive"
                  >
                    <TrashIcon size={14} />
                    Delete
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
