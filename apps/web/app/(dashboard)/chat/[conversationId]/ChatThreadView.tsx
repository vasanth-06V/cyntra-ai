"use client";

import { useEffect, useState } from "react";
import { apiClient, ApiError } from "@/lib/api-client/fastapi";
import { ChatWindow } from "@/components/chat/ChatWindow";
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
    return <p className="p-6 text-sm text-destructive">{error}</p>;
  }

  if (messages === null) {
    return <p className="p-6 text-sm text-muted-foreground">Loading…</p>;
  }

  return (
    <div className="h-[calc(100vh-8.5rem)]">
      <ChatWindow
        conversationId={conversationId}
        initialMessages={messages}
        validProviders={validProviders}
      />
    </div>
  );
}
