"use client";

import { useEffect, useState } from "react";
import { apiClient, ApiError } from "@/lib/api-client/fastapi";
import { ChatWindow } from "@/components/chat/ChatWindow";
import Link from "next/link";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { RefreshIcon } from "@/components/ui/icons";
import { Skeleton } from "@/components/ui/Skeleton";
import type { ChatMessage } from "@/types/chat";
import type { ProviderKey, ProviderName } from "@/types/keys";

export function ChatThreadView({ conversationId }: { conversationId: string }) {
  const [messages, setMessages] = useState<ChatMessage[] | null>(null);
  const [validProviders, setValidProviders] = useState<ProviderName[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

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
  }, [conversationId, attempt]);

  if (error) {
    return (
      <div className="flex max-w-xl flex-col items-start gap-3">
        <Alert role="alert" className="w-full">
          {error}
        </Alert>
        <div className="flex items-center gap-3">
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
          <Link href="/chat" className="text-sm font-medium text-primary underline-offset-4 hover:underline">
            Back to chats
          </Link>
        </div>
      </div>
    );
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
