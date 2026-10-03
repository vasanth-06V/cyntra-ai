"use client";

import { useEffect, useRef, useState } from "react";
import { apiClient, ApiError } from "@/lib/api-client/fastapi";
import { ChatWindow } from "@/components/chat/ChatWindow";
import Link from "next/link";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { InlineRename } from "@/components/ui/InlineRename";
import { useToast } from "@/components/ui/Toast";
import { ArrowLeftIcon, PencilIcon, RefreshIcon } from "@/components/ui/icons";
import { MAX_CHAT_TITLE_LENGTH, validateChatTitle } from "@/lib/chat";
import { createClient } from "@/lib/supabase/client";
import { Skeleton } from "@/components/ui/Skeleton";
import type { ChatMessage, Conversation } from "@/types/chat";
import type { ProviderKey, ProviderName } from "@/types/keys";

export function ChatThreadView({ conversationId }: { conversationId: string }) {
  const [messages, setMessages] = useState<ChatMessage[] | null>(null);
  const [validProviders, setValidProviders] = useState<ProviderName[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const { toast } = useToast();
  const [title, setTitle] = useState<string | null>(null);
  const [renaming, setRenaming] = useState(false);
  const renameOpener = useRef<HTMLButtonElement>(null);

  // The title only decorates the header, so a failure here is silent: the thread still works.
  useEffect(() => {
    let cancelled = false;
    Promise.resolve(createClient().from("conversations").select("title").eq("id", conversationId).maybeSingle())
      .then((res: { data?: { title?: string | null } | null }) => {
        if (!cancelled) setTitle(res?.data?.title ?? null);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [conversationId]);

  async function renameConversation(value: string) {
    try {
      const updated = await apiClient.patch<Conversation>(`/chat/conversations/${conversationId}`, { title: value.trim() });
      setTitle(updated?.title ?? value.trim());
      toast({ tone: "success", title: "Chat renamed" });
    } catch (err) {
      throw new Error(err instanceof ApiError ? err.message : "Could not rename this chat.");
    }
  }

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
    <div className="fill-screen flex flex-col overflow-hidden rounded-xl border border-border bg-card shadow-sm">
      <div className="flex min-h-12 items-center gap-2 border-b border-border px-3 py-2">
        <Link
          href="/chat"
          aria-label="Back to chats"
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-muted-foreground hover:bg-secondary hover:text-foreground"
        >
          <ArrowLeftIcon size={16} />
        </Link>
        {renaming ? (
          <InlineRename
            className="flex-1"
            initialValue={title ?? ""}
            label="New title for this chat"
            placeholder="Chat title"
            maxLength={MAX_CHAT_TITLE_LENGTH}
            validate={validateChatTitle}
            onSave={renameConversation}
            onClose={() => {
              setRenaming(false);
              setTimeout(() => renameOpener.current?.focus(), 0);
            }}
          />
        ) : (
          <>
            <h1 className="min-w-0 flex-1 truncate text-sm font-semibold">{title || "Untitled conversation"}</h1>
            <Button
              ref={renameOpener}
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setRenaming(true)}
              aria-label="Rename this chat"
              className="text-muted-foreground"
            >
              <PencilIcon size={14} />
              Rename
            </Button>
          </>
        )}
      </div>
      <div className="min-h-0 flex-1">
        <ChatWindow
          conversationId={conversationId}
          initialMessages={messages}
          validProviders={validProviders}
        />
      </div>
    </div>
  );
}
