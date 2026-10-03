"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { apiClient, ApiError } from "@/lib/api-client/fastapi";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { ChatIcon, SendIcon } from "@/components/ui/icons";
import { MessageBubble } from "./MessageBubble";
import type { ChatMessage } from "@/types/chat";
import { PROVIDER_INFO, type ProviderName } from "@/types/keys";

export function ChatWindow({
  conversationId,
  initialMessages,
  validProviders,
}: {
  conversationId: string;
  initialMessages: ChatMessage[];
  validProviders: ProviderName[];
}) {
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [provider, setProvider] = useState<ProviderName | undefined>(validProviders[0]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView?.({ behavior: "smooth", block: "end" });
  }, [messages]);

  async function handleSend(e?: React.FormEvent) {
    e?.preventDefault();
    const content = input.trim();
    if (!content || !provider || sending) return;

    setError(null);
    setInput("");
    setSending(true);

    const userMessage: ChatMessage = {
      id: `local-${Date.now()}`,
      role: "user",
      provider: null,
      content,
      created_at: new Date().toISOString(),
    };
    const assistantId = `local-${Date.now()}-assistant`;
    setMessages((prev) => [
      ...prev,
      userMessage,
      { id: assistantId, role: "assistant", provider, content: "", created_at: "" },
    ]);

    let received = false;
    try {
      for await (const chunk of apiClient.streamPost(
        `/chat/conversations/${conversationId}/messages`,
        { provider, content }
      )) {
        received = true;
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, content: m.content + chunk } : m
          )
        );
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
      if (!received) {
        // Nothing was saved for a send that failed before the first word: drop
        // both local bubbles and give the draft back so it can be retried.
        setMessages((prev) =>
          prev.filter((m) => m.id !== assistantId && m.id !== userMessage.id)
        );
        setInput(content);
      }
      // Once words arrived the server keeps the partial exchange, so keep what
      // the user saw (retrying would otherwise store the question twice).
    } finally {
      setSending(false);
      // The field was disabled while the reply streamed; hand the cursor back.
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div role="log" aria-live="polite" className="flex-1 space-y-4 overflow-y-auto scroll-smooth p-4 sm:p-6">
        {messages.length === 0 && (
          <EmptyState className="mx-auto mt-6 max-w-md border-0 bg-transparent" icon={<ChatIcon size={20} />} title="Start the conversation">
            Ask anything, or paste an answer you want feedback on.
          </EmptyState>
        )}
        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} copyable />
        ))}
        <div ref={bottomRef} />
      </div>

      {error && (
        <Alert role="alert" className="mx-3 mb-0 mt-3">
          {error}
        </Alert>
      )}

      {validProviders.length === 0 && (
        <p className="mx-3 mt-3 text-sm text-muted-foreground">
          No working key yet.{" "}
          <Link href="/settings/api-keys" className="font-medium text-primary underline-offset-4 hover:underline">
            Add one in API Keys
          </Link>{" "}
          to start chatting.
        </p>
      )}

      <form onSubmit={handleSend} className="flex items-end gap-2 border-t border-border bg-background/50 p-3">
        <select
          value={provider ?? ""}
          aria-label="Model provider"
          onChange={(e) => setProvider(e.target.value as ProviderName)}
          disabled={validProviders.length === 0}
          className="field h-10 max-w-[8.5rem] sm:max-w-none"
        >
          {validProviders.length === 0 ? (
            <option value="">No valid keys</option>
          ) : (
            validProviders.map((p) => (
              <option key={p} value={p}>
                {PROVIDER_INFO[p].label}
              </option>
            ))
          )}
        </select>
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            // Enter sends, Shift+Enter adds a line (not while an IME is composing).
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              void handleSend();
            }
          }}
          placeholder="Message… (Enter to send, Shift+Enter for a new line)"
          aria-label="Message"
          rows={1}
          maxLength={8000}
          readOnly={sending}
          disabled={!provider}
          className="field max-h-40 min-h-10 min-w-0 flex-1 resize-none [field-sizing:content]"
        />
        <Button type="submit" loading={sending} disabled={!provider || !input.trim()}>
          <SendIcon size={16} />
          Send
        </Button>
      </form>
    </div>
  );
}
