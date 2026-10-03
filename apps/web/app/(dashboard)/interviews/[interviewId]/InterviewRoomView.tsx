"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { apiClient, ApiError } from "@/lib/api-client/fastapi";
import { Button } from "@/components/ui/Button";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { CodeEditorPanel } from "@/components/interview/CodeEditorPanel";
import { PhaseTimer } from "@/components/interview/PhaseTimer";
import type { ChatMessage } from "@/types/chat";
import type { Interview, TranscriptEntry, TurnResponse } from "@/types/interviews";

function toChatMessage(entry: TranscriptEntry): ChatMessage {
  return {
    id: entry.id,
    role: entry.speaker === "ai" ? "assistant" : "user",
    provider: null,
    content: entry.text,
    created_at: entry.created_at,
  };
}

export function InterviewRoomView({ interviewId }: { interviewId: string }) {
  const router = useRouter();
  const [interview, setInterview] = useState<Interview | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [phase, setPhase] = useState("");
  const [minutesRemaining, setMinutesRemaining] = useState(60);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [sendError, setSendError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  // The coding editor appears beside the chat while a problem is active; the
  // chat pauses while a submitted solution is being reviewed.
  const [codeActive, setCodeActive] = useState(false);
  const [reviewing, setReviewing] = useState(false);

  const reloadTranscript = useCallback(() => {
    apiClient
      .get<TranscriptEntry[]>(`/interviews/${interviewId}/transcript`)
      .then((transcript) => setMessages(transcript.map(toChatMessage)))
      .catch(() => {
        // the next turn reloads it anyway
      });
  }, [interviewId]);

  useEffect(() => {
    Promise.all([
      apiClient.get<Interview>(`/interviews/${interviewId}`),
      apiClient.get<TranscriptEntry[]>(`/interviews/${interviewId}/transcript`),
    ])
      .then(([iv, transcript]) => {
        setInterview(iv);
        setMessages(transcript.map(toChatMessage));
        setPhase(iv.phase ?? "");
        if (iv.ends_at) {
          const remaining = (new Date(iv.ends_at).getTime() - Date.now()) / 60000;
          setMinutesRemaining(Math.max(0, remaining));
        }
      })
      .catch((err) =>
        setLoadError(err instanceof ApiError ? err.message : "Could not load this interview.")
      );
  }, [interviewId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Ticks the displayed timer down client-side between turns, so it doesn't
  // sit frozen while the candidate is composing an answer.
  useEffect(() => {
    if (!interview?.ends_at) return;
    const endsAtMs = new Date(interview.ends_at).getTime();
    const tick = () => setMinutesRemaining(Math.max(0, (endsAtMs - Date.now()) / 60000));
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [interview?.ends_at]);

  async function handleComplete() {
    try {
      await apiClient.post(`/interviews/${interviewId}/complete`);
      setInterview((prev) => (prev ? { ...prev, status: "completed" } : prev));
    } catch (err) {
      setSendError(err instanceof ApiError ? err.message : "Could not end the interview.");
    }
  }

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    const content = input.trim();
    if (!content || sending || reviewing || interview?.status !== "in_progress") return;

    const localId = `local-${Date.now()}`;
    setInput("");
    setSending(true);
    setSendError(null);
    setMessages((prev) => [
      ...prev,
      { id: localId, role: "user", provider: null, content, created_at: "" },
    ]);

    try {
      const response = await apiClient.post<TurnResponse>(
        `/interviews/${interviewId}/turns`,
        { content }
      );
      setPhase(response.phase);
      setMessages((prev) => [
        ...prev,
        {
          id: `local-${Date.now()}-ai`,
          role: "assistant",
          provider: interview?.provider ?? null,
          content: response.message,
          created_at: "",
        },
      ]);
      if (response.is_final_phase && response.minutes_remaining <= 0) {
        await handleComplete();
      }
    } catch (err) {
      // Keep the room; take the unsent bubble back out and restore the draft
      // so the candidate can retry.
      setMessages((prev) => prev.filter((m) => m.id !== localId));
      setInput(content);
      setSendError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setSending(false);
    }
  }

  if (loadError) return <p role="alert" className="p-6 text-sm text-destructive">{loadError}</p>;
  if (!interview) return <p className="p-6 text-sm text-muted-foreground">Loading…</p>;

  const isActive = interview.status === "in_progress";

  return (
    <div className="flex h-[calc(100vh-8.5rem)] flex-col">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <PhaseTimer phase={phase || interview.status} minutesRemaining={minutesRemaining} />
        {isActive && (
          <button
            type="button"
            onClick={handleComplete}
            className="text-sm text-muted-foreground hover:text-destructive cursor-pointer"
          >
            End interview
          </button>
        )}
      </div>

      <div className={`flex min-h-0 flex-1 flex-col ${codeActive ? "lg:grid lg:grid-cols-2" : ""}`}>
      <div className="flex min-h-0 flex-1 flex-col">
      <div role="log" aria-live="polite" className="flex-1 space-y-3 overflow-y-auto p-4">
        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}
        <div ref={bottomRef} />
      </div>

      {isActive ? (
        <form onSubmit={handleSend} className="flex items-center gap-2 border-t border-border p-3">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Your answer…"
            aria-label="Your answer"
            maxLength={4000}
            disabled={sending || reviewing}
            className="flex-1 rounded-lg border border-border bg-transparent px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
          />
          <Button type="submit" disabled={sending || reviewing || !input.trim()}>
            {sending ? "Thinking…" : "Send"}
          </Button>
        </form>
      ) : (
        <div className="border-t border-border p-4 text-center">
          <p className="mb-2 text-sm text-muted-foreground">
            This interview is {interview.status}.
          </p>
          <Button onClick={() => router.push("/interviews")}>Back to interviews</Button>
        </div>
      )}
      </div>

      {isActive && (
        <CodeEditorPanel
          interviewId={interviewId}
          refreshKey={`${phase}:${messages.length}`}
          onBusyChange={setReviewing}
          onReviewed={reloadTranscript}
          onProblemChange={setCodeActive}
        />
      )}
      </div>

      {sendError && (
        <p role="alert" className="px-4 pb-3 text-sm text-destructive">
          {sendError}
        </p>
      )}
    </div>
  );
}
