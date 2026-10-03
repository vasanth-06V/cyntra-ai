"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { apiClient, ApiError } from "@/lib/api-client/fastapi";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useConfirm } from "@/components/ui/ConfirmProvider";
import { useToast } from "@/components/ui/Toast";
import { RefreshIcon, TrashIcon } from "@/components/ui/icons";
import { Skeleton } from "@/components/ui/Skeleton";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { CodeEditorPanel } from "@/components/interview/CodeEditorPanel";
import { PhaseTimer } from "@/components/interview/PhaseTimer";
import { VoiceBar } from "@/components/interview/VoiceBar";
import { DEFAULT_SETTINGS, loadSettings, saveSettings, type VoiceSettings } from "@/lib/voice/settings";
import { useVoice } from "@/lib/voice/useVoice";
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
  const confirm = useConfirm();
  const { toast } = useToast();
  const [interview, setInterview] = useState<Interview | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [phase, setPhase] = useState("");
  const [minutesRemaining, setMinutesRemaining] = useState(60);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [sendError, setSendError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [cancelling, setCancelling] = useState(false);
  const answerRef = useRef<HTMLTextAreaElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  // The coding editor appears beside the chat while a problem is active; the
  // chat pauses while a submitted solution is being reviewed.
  const [codeActive, setCodeActive] = useState(false);
  const [reviewing, setReviewing] = useState(false);

  // Voice (browser speech recognition in, speech synthesis out) is only an I/O
  // layer: spoken answers go through the same turn endpoint as typed ones.
  const [voiceSettings, setVoiceSettings] = useState<VoiceSettings>(DEFAULT_SETTINGS);
  const messagesRef = useRef<ChatMessage[]>([]);
  const sendRef = useRef<(text: string) => void>(() => {});
  const speakRef = useRef<(text: string) => void>(() => {});

  const lastInterviewerText = useCallback(() => {
    const last = [...messagesRef.current].reverse().find((m) => m.role === "assistant");
    return last ? last.content : null;
  }, []);

  const reloadTranscript = useCallback(() => {
    apiClient
      .get<TranscriptEntry[]>(`/interviews/${interviewId}/transcript`)
      .then((transcript) => {
        setMessages(transcript.map(toChatMessage));
        const last = transcript[transcript.length - 1];
        if (last && last.speaker === "ai") speakRef.current(last.text);
      })
      .catch(() => {
        // the next turn reloads it anyway
      });
  }, [interviewId]);

  useEffect(() => {
    messagesRef.current = messages;
  });

  // Remembered per browser; read after mount so server and client render alike.
  useEffect(() => {
    const t = setTimeout(() => setVoiceSettings(loadSettings()), 0);
    return () => clearTimeout(t);
  }, []);

  const isActive = interview?.status === "in_progress";
  const voice = useVoice({
    active: Boolean(isActive) && voiceSettings.enabled,
    busy: sending || reviewing,
    settings: voiceSettings,
    onUtterance: (text) => sendRef.current(text),
    lastInterviewerText,
  });
  useEffect(() => {
    speakRef.current = (text) => void voice.speak(text);
  });

  function changeVoiceSettings(next: VoiceSettings) {
    setVoiceSettings(next);
    saveSettings(next);
  }

  function enableVoice() {
    // Runs inside the click, which is what lets the browser speak at all.
    changeVoiceSettings({ ...voiceSettings, enabled: true, consented: true });
    const last = lastInterviewerText();
    const endsWithInterviewer = messagesRef.current[messagesRef.current.length - 1]?.role === "assistant";
    if (last && endsWithInterviewer) void voice.speak(last);
  }

  useEffect(() => {
    Promise.all([
      apiClient.get<Interview>(`/interviews/${interviewId}`),
      apiClient.get<TranscriptEntry[]>(`/interviews/${interviewId}/transcript`),
    ])
      .then(([iv, transcript]) => {
        setInterview(iv);
        setMessages(transcript.map(toChatMessage));
        setLoadError(null);
        setPhase(iv.phase ?? "");
        if (iv.ends_at) {
          const remaining = (new Date(iv.ends_at).getTime() - Date.now()) / 60000;
          setMinutesRemaining(Math.max(0, remaining));
        }
      })
      .catch((err) =>
        setLoadError(err instanceof ApiError ? err.message : "Could not load this interview.")
      );
  }, [interviewId, attempt]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView?.({ behavior: "smooth", block: "end" });
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

  async function completeInterview() {
    try {
      await apiClient.post(`/interviews/${interviewId}/complete`);
    } catch (err) {
      throw new Error(err instanceof ApiError ? err.message : "Could not end the interview.");
    }
    setInterview((prev) => (prev ? { ...prev, status: "completed" } : prev));
  }

  async function handleEnd() {
    const ok = await confirm({
      title: "End the interview now?",
      description:
        "This stops the timer and closes the room. You can't continue afterwards, but you can get a report for the answers so far.",
      confirmLabel: "End interview",
      tone: "danger",
      onConfirm: completeInterview,
    });
    if (ok) toast({ tone: "success", title: "Interview ended", description: "You can now get your report." });
  }

  async function deleteInterview() {
    try {
      await apiClient.delete(`/interviews/${interviewId}`);
    } catch (err) {
      throw new Error(err instanceof ApiError ? err.message : "Could not delete this interview.");
    }
  }

  async function handleDelete() {
    const ok = await confirm({
      title: "Delete this interview?",
      description:
        "The transcript, any code you submitted and the report for this interview are removed too. This can't be undone.",
      confirmLabel: "Delete interview",
      tone: "danger",
      onConfirm: deleteInterview,
    });
    if (ok) {
      toast({ tone: "success", title: "Interview deleted" });
      router.push("/interviews");
    }
  }

  async function handleCancelSetup() {
    setCancelling(true);
    try {
      const updated = await apiClient.post<Interview>(`/interviews/${interviewId}/abort`);
      setInterview(updated);
      toast({ tone: "info", title: "Setup cancelled" });
    } catch (err) {
      if (err instanceof ApiError && err.code === "interview_not_cancellable") {
        toast({ tone: "info", title: "This interview is no longer being set up", description: "Reloading it." });
        setInterview(null);
        setAttempt((n) => n + 1);
      } else {
        toast({
          tone: "error",
          title: "Could not cancel the setup",
          description: err instanceof ApiError ? err.message : "Please try again.",
        });
      }
    } finally {
      setCancelling(false);
    }
  }

  // Time ran out on its own: no question to ask, just close it.
  async function autoComplete() {
    try {
      await completeInterview();
    } catch (err) {
      setSendError(err instanceof Error ? err.message : "Could not end the interview.");
    }
  }

  function handleSend(e: React.FormEvent) {
    e.preventDefault();
    void sendContent(input.trim());
  }

  async function sendContent(content: string) {
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
      speakRef.current(response.message);
      if (response.is_final_phase && response.minutes_remaining <= 0) {
        await autoComplete();
      }
    } catch (err) {
      // Keep the room; take the unsent bubble back out and restore the draft
      // so the candidate can retry.
      setMessages((prev) => prev.filter((m) => m.id !== localId));
      setInput(content);
      setSendError(err instanceof ApiError ? err.message : "Something went wrong.");
      if (err instanceof ApiError && err.code === "interview_ended") {
        // The server closed the interview (time is up): show it as finished.
        setInterview((prev) => (prev ? { ...prev, status: "completed" } : prev));
      }
    } finally {
      setSending(false);
    }
  }

  useEffect(() => {
    sendRef.current = (text) => void sendContent(text);
  });

  if (loadError) {
    return (
      <div className="flex max-w-xl flex-col items-start gap-3">
        <Alert role="alert" className="w-full">
          {loadError}
        </Alert>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            setLoadError(null);
            setAttempt((n) => n + 1);
          }}
        >
          <RefreshIcon size={14} />
          Try again
        </Button>
      </div>
    );
  }
  if (!interview) {
    return (
      <div role="status" className="fill-screen flex flex-col gap-4 rounded-2xl border border-border bg-card p-5 shadow-md">
        <span className="sr-only">Loading…</span>
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-16 w-2/3" />
        <Skeleton className="ml-auto h-12 w-1/2" />
        <Skeleton className="mt-auto h-12 w-full" />
      </div>
    );
  }

  // Who has the floor right now. Purely visual: the voice bar and live log
  // already announce the same changes to assistive tech.
  const turn: { label: string; tone: "info" | "brand" | "success" | "neutral" } = !isActive
    ? { label: `Interview ${interview.status.replace(/_/g, " ")}`, tone: "neutral" }
    : reviewing
      ? { label: "Reviewing your code", tone: "info" }
      : sending
        ? { label: "Interviewer is thinking", tone: "info" }
        : voice.speaking
          ? { label: "Interviewer is speaking", tone: "brand" }
          : voice.listening
            ? { label: "Listening to you", tone: "success" }
            : { label: "Your turn", tone: "success" };

  return (
    <div
      className={`fill-screen flex flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-md ${
        codeActive ? "max-lg:!h-auto" : ""
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b border-border bg-background/60 px-4 py-3">
        <PhaseTimer phase={phase || interview.status} minutesRemaining={minutesRemaining} />
        <div className="flex items-center gap-2">
          <Badge tone={turn.tone} className="gap-1.5" aria-hidden="true">
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                turn.tone === "success"
                  ? "bg-success"
                  : turn.tone === "info"
                    ? "bg-info"
                    : turn.tone === "brand"
                      ? "bg-primary"
                      : "bg-muted-foreground"
              }`}
            />
            {turn.label}
          </Badge>
          {isActive && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => void handleEnd()}
              className="text-muted-foreground hover:bg-destructive-soft hover:text-destructive"
            >
              End interview
            </Button>
          )}
        </div>
      </div>

      <div
        className={`flex min-h-0 flex-1 flex-col ${
          codeActive ? "lg:grid lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]" : ""
        }`}
      >
        <div className={`flex min-h-0 min-w-0 flex-1 flex-col ${codeActive ? "max-lg:h-[30rem] max-lg:flex-none" : ""}`}>
          <div
            role="log"
            aria-live="polite"
            className="flex-1 space-y-4 overflow-y-auto scroll-smooth bg-secondary/40 p-4 sm:p-6"
          >
            {messages.map((m) => (
              <MessageBubble key={m.id} message={m} assistantLabel="Interviewer" />
            ))}
            {sending && (
              <div aria-hidden="true" className="animate-fade-in">
                <MessageBubble
                  message={{ id: "typing", role: "assistant", provider: null, content: "", created_at: "" }}
                  assistantLabel="Interviewer"
                />
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {isActive && (
            // Reserve the bar's resting height so switching voice on/off or the unsupported note does not shove the chat around.
            <div className="min-h-[3.25rem] bg-background/60">
            <VoiceBar
              voice={voice}
              settings={voiceSettings}
              onSettingsChange={changeVoiceSettings}
              onEnable={enableVoice}
              onDisable={() => changeVoiceSettings({ ...voiceSettings, enabled: false })}
              onSendCaption={voice.sendNow}
              reviewing={reviewing}
              sending={sending}
            />
            </div>
          )}

          {isActive ? (
            <>
              {sendError && (
                <Alert role="alert" className="mx-3 mb-0 mt-2">
                  {sendError}
                </Alert>
              )}
              <form onSubmit={handleSend} className="flex items-end gap-2 border-t border-border bg-card p-3">
                <textarea
                  ref={answerRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    // Enter sends, Shift+Enter adds a line (not while an IME is composing).
                    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                      e.preventDefault();
                      void sendContent(input.trim());
                    }
                  }}
                  placeholder="Your answer… (Enter to send, Shift+Enter for a new line)"
                  aria-label="Your answer"
                  rows={1}
                  maxLength={4000}
                  readOnly={sending}
                  disabled={reviewing}
                  className="field max-h-40 min-h-10 min-w-0 flex-1 resize-none [field-sizing:content]"
                />
                <Button type="submit" loading={sending} disabled={reviewing || !input.trim()}>
                  {sending ? "Thinking…" : "Send"}
                </Button>
              </form>
            </>
          ) : (
            <div className="border-t border-border bg-card p-5 text-center">
              <p className="mb-3 text-sm text-muted-foreground">
                {interview.status === "setting_up"
                  ? "This interview is still being set up. If it is stuck, you can cancel the setup and start a new one."
                  : interview.status === "aborted"
                    ? "This interview was stopped before it finished."
                    : "This interview is finished."}
              </p>
              <div className="flex flex-wrap justify-center gap-2">
                {interview.status === "setting_up" && (
                  <Button
                    variant="secondary"
                    onClick={() => {
                      setInterview(null);
                      setAttempt((n) => n + 1);
                    }}
                  >
                    <RefreshIcon size={14} />
                    Refresh
                  </Button>
                )}
                {interview.status === "setting_up" && (
                  <Button variant="outline" onClick={() => void handleCancelSetup()} loading={cancelling}>
                    {cancelling ? "Cancelling…" : "Cancel setup"}
                  </Button>
                )}
                {interview.status === "completed" && (
                  <Button onClick={() => router.push("/reports")}>Get my report</Button>
                )}
                <Button variant="outline" onClick={() => router.push("/interviews")}>
                  Back to interviews
                </Button>
                {(interview.status === "completed" || interview.status === "aborted") && (
                  <Button
                    variant="ghost"
                    onClick={() => void handleDelete()}
                    className="text-muted-foreground hover:bg-destructive-soft hover:text-destructive"
                  >
                    <TrashIcon size={14} />
                    Delete interview
                  </Button>
                )}
              </div>
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

      {sendError && !isActive && (
        <Alert role="alert" className="m-3 mt-0">
          {sendError}
        </Alert>
      )}
    </div>
  );
}
