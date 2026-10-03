"use client";

import { useEffect, useState } from "react";
import { apiClient, ApiError } from "@/lib/api-client/fastapi";
import { ChatWindow } from "@/components/chat/ChatWindow";
import { Alert } from "@/components/ui/Alert";
import { Skeleton } from "@/components/ui/Skeleton";
import type { ChatMessage } from "@/types/chat";
import type { ProviderKey, ProviderName } from "@/types/keys";

export function ChatThreadView({ conversationId }: { conversationId: string }) {
  const [messages, setMessages] = useState<ChatMessage[] | null>(null);
  const [validProviders, setValidProviders] = useState<ProviderName[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      apiClient.get<ChatMessage[]>(`/chat/conversations/${conversationId}/messages`),
      apiClient.get<ProviderKey[]>("/keys"),
    ])
      .then(([msgs, keys]) => {
        setMessages(msgs);
        setValidProviders(
          keys
            .filter((k) => k.slot === "primary" && k.is_valid)
            .map((k) => k.provider)
        );
      })
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Could not load this conversation.")
      );
  }, [conversationId]);

  if (error) {
    return <Alert role="alert">{error}</Alert>;
  }

  if (messages === null) {
    return (
      <div role="status" className="fill-screen flex flex-col gap-4 rounded-xl border border-border bg-card p-5 shadow-sm">
        <span className="sr-only">Loading…</span>
        <Skeleton className="h-12 w-2/3" />
        <Skeleton className="ml-auto h-12 w-1/2" />
        <Skeleton className="h-20 w-3/4" />
      </div>
    );
  }

  return (
    <div className="fill-screen overflow-hidden rounded-xl border border-border bg-card shadow-sm">
      <ChatWindow
        conversationId={conversationId}
        initialMessages={messages}
        validProviders={validProviders}
      />
    </div>
  );
}
