"use client";

import { useEffect, useRef, useState } from "react";
import { apiClient, ApiError } from "@/lib/api-client/fastapi";
import { Button } from "@/components/ui/Button";
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

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
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
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div role="log" aria-live="polite" className="flex-1 space-y-3 overflow-y-auto p-4">
        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}
        <div ref={bottomRef} />
      </div>

      <form onSubmit={handleSend} className="flex items-center gap-2 border-t border-border p-3">
        <select
          value={provider ?? ""}
          aria-label="Model provider"
          onChange={(e) => setProvider(e.target.value as ProviderName)}
          disabled={validProviders.length === 0}
          className="rounded-lg border border-border bg-transparent px-2 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
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
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Message…"
          aria-label="Message"
          disabled={!provider || sending}
          className="flex-1 rounded-lg border border-border bg-transparent px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
        />
        <Button type="submit" disabled={!provider || sending || !input.trim()}>
          Send
        </Button>
      </form>

      {error && (
        <p role="alert" className="px-4 pb-3 text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
