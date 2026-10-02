"use client";

import { useEffect, useState } from "react";
import { apiClient, ApiError } from "@/lib/api-client/fastapi";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import {
  INTERVIEW_TYPE_LABELS,
  type InterviewType,
  type Question,
} from "@/types/interviews";

const INTERVIEW_TYPES = Object.keys(INTERVIEW_TYPE_LABELS) as InterviewType[];

export function QuestionBankView() {
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
  const [testCasesText, setTestCasesText] = useState("");
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
    setTestCasesText("");
    setFormError(null);
  }

  function startEdit(q: Question) {
    setEditingId(q.id);
    setType(q.type);
    setQuestionText(q.question);
    setTagsText((q.tags ?? []).join(", "));
    setTopicText(q.topic ?? "");
    setDifficulty(q.difficulty ? String(q.difficulty) : "");
    setTestCasesText(q.test_cases ? JSON.stringify(q.test_cases, null, 2) : "");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);

    let testCases = null;
    if (testCasesText.trim()) {
      try {
        testCases = JSON.parse(testCasesText);
      } catch {
        setFormError(
          'Test cases must be valid JSON, e.g. [{"input": "...", "output": "..."}]'
        );
        return;
      }
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
          test_cases: testCases,
          tags,
          topic: topicText.trim() || undefined,
          difficulty: difficulty ? Number(difficulty) : undefined,
        });
      } else {
        await apiClient.post("/interviews/question-bank", {
          type,
          question: questionText,
          test_cases: testCases,
          tags,
          topic: topicText.trim() || undefined,
          difficulty: difficulty ? Number(difficulty) : undefined,
        });
      }
      resetForm();
      await load();
    } catch (err) {
      setFormError(
        err instanceof ApiError ? err.message : "Could not save this question."
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: string) {
    const previous = questions;
    setQuestions((prev) => prev.filter((q) => q.id !== id));
    try {
      await apiClient.delete(`/interviews/question-bank/${id}`);
    } catch {
      setQuestions(previous);
    }
  }

  const visibleQuestions =
    filterType === "all" ? questions : questions.filter((q) => q.type === filterType);

  return (
    <div>
      <h1 className="text-2xl font-semibold">Question Bank</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Manage interview questions and test cases. Saving requires a valid Gemini
        key (each question is embedded for RAG selection).
      </p>

      <Card className="mt-6 p-5">
        <h2 className="text-sm font-medium">
          {editingId ? "Edit question" : "Add a question"}
        </h2>
        <form onSubmit={handleSubmit} className="mt-3 flex flex-col gap-3">
          <select
            value={type}
            onChange={(e) => setType(e.target.value as InterviewType)}
            disabled={!!editingId}
            className="rounded-lg border border-border bg-transparent px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
          >
            {INTERVIEW_TYPES.map((t) => (
              <option key={t} value={t}>
                {INTERVIEW_TYPE_LABELS[t]}
              </option>
            ))}
          </select>

          <textarea
            value={questionText}
            onChange={(e) => setQuestionText(e.target.value)}
            placeholder="Question text…"
            rows={3}
            required
            className="rounded-lg border border-border bg-transparent px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
          />

          <input
            value={tagsText}
            onChange={(e) => setTagsText(e.target.value)}
            placeholder="Tags, comma separated (optional)"
            className="rounded-lg border border-border bg-transparent px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
          />

          <div className="flex gap-3">
            <input
              value={topicText}
              onChange={(e) => setTopicText(e.target.value)}
              placeholder="Topic, e.g. arrays, caching, conflict (optional)"
              aria-label="Topic"
              maxLength={60}
              className="flex-1 rounded-lg border border-border bg-transparent px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
            />
            <select
              value={difficulty}
              onChange={(e) => setDifficulty(e.target.value)}
              aria-label="Difficulty"
              className="rounded-lg border border-border bg-transparent px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="">Difficulty</option>
              {[1, 2, 3, 4, 5].map((d) => (
                <option key={d} value={d}>
                  {d} {d === 1 ? "(easy)" : d === 5 ? "(hard)" : ""}
                </option>
              ))}
            </select>
          </div>

          <textarea
            value={testCasesText}
            onChange={(e) => setTestCasesText(e.target.value)}
            placeholder='Test cases as JSON (optional), e.g. [{"input": "1,2", "output": "3"}]'
            rows={4}
            className="rounded-lg border border-border bg-transparent px-3 py-2 font-mono text-xs outline-none focus:ring-2 focus:ring-ring"
          />

          {formError && <p className="text-sm text-destructive">{formError}</p>}

          <div className="flex gap-2">
            <Button type="submit" disabled={saving || !questionText.trim()}>
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

      <div className="mt-6 flex items-center justify-between">
        <h2 className="text-sm font-medium text-muted-foreground">
          {visibleQuestions.length} question{visibleQuestions.length === 1 ? "" : "s"}
        </h2>
        <select
          value={filterType}
          onChange={(e) => setFilterType(e.target.value as InterviewType | "all")}
          className="rounded-lg border border-border bg-transparent px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-ring"
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
        <p className="mt-4 text-sm text-muted-foreground">Loading…</p>
      ) : loadError ? (
        <p className="mt-4 text-sm text-destructive">{loadError}</p>
      ) : visibleQuestions.length === 0 ? (
        <div className="mt-4 rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
          No questions yet.
        </div>
      ) : (
        <div className="mt-4 flex flex-col gap-2">
          {visibleQuestions.map((q) => (
            <Card key={q.id} className="p-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <span className="text-xs text-muted-foreground">
                    {INTERVIEW_TYPE_LABELS[q.type]}
                  </span>
                  <p className="text-sm">{q.question}</p>
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
                <div className="flex shrink-0 gap-3">
                  <button
                    type="button"
                    onClick={() => startEdit(q)}
                    className="text-sm text-muted-foreground hover:text-foreground cursor-pointer"
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDelete(q.id)}
                    className="text-sm text-muted-foreground hover:text-destructive cursor-pointer"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
