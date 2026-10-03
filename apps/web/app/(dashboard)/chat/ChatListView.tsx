"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { apiClient, ApiError } from "@/lib/api-client/fastapi";
import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/Alert";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { ListSkeleton } from "@/components/ui/Skeleton";
import { ChatIcon, ChevronRightIcon } from "@/components/ui/icons";
import type { Conversation } from "@/types/chat";

export function ChatListView() {
  const router = useRouter();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiClient
      .get<Conversation[]>("/chat/conversations")
      .then(setConversations)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Could not load conversations.")
      )
      .finally(() => setLoading(false));
  }, []);

  async function newChat() {
    setCreating(true);
    try {
      const conversation = await apiClient.post<Conversation>("/chat/conversations", {});
      router.push(`/chat/${conversation.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not start a new chat.");
      setCreating(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="Chat"
        description="Talk through ideas, practise answers or get unstuck with any provider you've connected."
        actions={
          <Button onClick={newChat} loading={creating}>
            {creating ? "Starting…" : "New chat"}
          </Button>
        }
      />

      {loading ? (
        <ListSkeleton className="mt-6" rows={4} />
      ) : error ? (
        <Alert role="alert" className="mt-6">
          {error}
        </Alert>
      ) : conversations.length === 0 ? (
        <EmptyState className="mt-6" icon={<ChatIcon size={20} />} title="No conversations yet">
          No conversations yet -- start one above.
        </EmptyState>
      ) : (
        <div className="stagger mt-6 flex flex-col gap-2">
          {conversations.map((c) => (
            <Link key={c.id} href={`/chat/${c.id}`} className="group block rounded-xl">
              <Card interactive className="flex items-center justify-between gap-3 p-4">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{c.title || "Untitled conversation"}</p>
                  <p className="mt-0.5 text-xs text-muted-foreground tabular-nums">
                    {new Date(c.created_at).toLocaleString()}
                  </p>
                </div>
                <ChevronRightIcon
                  size={18}
                  className="shrink-0 text-muted-foreground transition-transform duration-200 group-hover:translate-x-0.5 group-hover:text-primary motion-reduce:transform-none"
                />
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
