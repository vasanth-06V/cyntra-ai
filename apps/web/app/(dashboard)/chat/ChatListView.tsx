"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { apiClient, ApiError } from "@/lib/api-client/fastapi";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
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
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Chat</h1>
        <Button onClick={newChat} disabled={creating}>
          {creating ? "Starting…" : "New chat"}
        </Button>
      </div>

      {loading ? (
        <p className="mt-6 text-sm text-muted-foreground">Loading…</p>
      ) : error ? (
        <p className="mt-6 text-sm text-destructive">{error}</p>
      ) : conversations.length === 0 ? (
        <div className="mt-6 rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
          No conversations yet -- start one above.
        </div>
      ) : (
        <div className="mt-6 flex flex-col gap-2">
          {conversations.map((c) => (
            <Link key={c.id} href={`/chat/${c.id}`}>
              <Card className="p-4 transition-colors hover:bg-secondary">
                <p className="text-sm font-medium">{c.title || "Untitled conversation"}</p>
                <p className="text-xs text-muted-foreground">
                  {new Date(c.created_at).toLocaleString()}
                </p>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
