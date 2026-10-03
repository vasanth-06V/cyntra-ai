"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiClient, ApiError } from "@/lib/api-client/fastapi";
import { createClient } from "@/lib/supabase/client";
import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/Alert";
import { useConfirm } from "@/components/ui/ConfirmProvider";
import { EmptyState } from "@/components/ui/EmptyState";
import { ListRow } from "@/components/ui/ListRow";
import { PageHeader } from "@/components/ui/PageHeader";
import { ListSkeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";
import { ChatIcon, PlusIcon, RefreshIcon, TrashIcon } from "@/components/ui/icons";
import type { Conversation } from "@/types/chat";

const PAGE_SIZE = 50;

export function ChatListView() {
  const router = useRouter();
  const confirm = useConfirm();
  const { toast } = useToast();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);

  useEffect(() => {
    apiClient
      .get<Conversation[]>("/chat/conversations")
      .then((list) => {
        setConversations(list);
        setHasMore(list.length >= PAGE_SIZE);
        setLoadError(null);
      })
      .catch((err) =>
        setLoadError(err instanceof ApiError ? err.message : "Could not load conversations.")
      )
      .finally(() => setLoading(false));
  }, [attempt]);

  // The API returns the newest 50 at a time; older ones are fetched on request.
  async function loadMore() {
    setLoadingMore(true);
    try {
      const next = await apiClient.get<Conversation[]>(
        `/chat/conversations?limit=${PAGE_SIZE}&offset=${conversations.length}`
      );
      setConversations((prev) => [...prev, ...next.filter((n) => !prev.some((p) => p.id === n.id))]);
      setHasMore(next.length >= PAGE_SIZE);
    } catch (err) {
      toast({
        tone: "error",
        title: "Could not load older chats",
        description: err instanceof ApiError ? err.message : "Please try again.",
      });
    } finally {
      setLoadingMore(false);
    }
  }

  async function newChat() {
    setCreating(true);
    try {
      const conversation = await apiClient.post<Conversation>("/chat/conversations", {});
      router.push(`/chat/${conversation.id}`);
    } catch (err) {
      toast({
        tone: "error",
        title: "Could not start a new chat",
        description: err instanceof ApiError ? err.message : "Please try again.",
      });
      setCreating(false);
    }
  }

  /**
   * There is no delete endpoint on the API, but conversations are protected by
   * row-level security (owner only, messages cascade), so the signed-in user's
   * own session can delete its own rows directly.
   */
  async function deleteConversation(c: Conversation) {
    const { data, error } = await createClient()
      .from("conversations")
      .delete()
      .eq("id", c.id)
      .select("id");
    if (error) throw new Error("Could not delete this conversation. Please try again.");
    if (!data || data.length === 0) throw new Error("That conversation no longer exists. Refresh the list.");
    setConversations((prev) => prev.filter((x) => x.id !== c.id));
  }

  async function handleDelete(c: Conversation) {
    const label = c.title || "Untitled conversation";
    const ok = await confirm({
      title: "Delete this conversation?",
      description: (
        <>
          <span className="font-medium text-foreground">{label}</span> and all of its messages will be removed for
          good.
        </>
      ),
      confirmLabel: "Delete conversation",
      tone: "danger",
      onConfirm: () => deleteConversation(c),
    });
    if (ok) toast({ tone: "success", title: "Conversation deleted" });
  }

  return (
    <div>
      <PageHeader
        title="Chat"
        description="Talk through ideas, practise answers or get unstuck with any provider you've connected."
        actions={
          <Button onClick={newChat} loading={creating}>
            {!creating && <PlusIcon size={16} />}
            {creating ? "Starting…" : "New chat"}
          </Button>
        }
      />

      {loading ? (
        <ListSkeleton className="mt-6" rows={4} />
      ) : loadError ? (
        <div className="mt-6 flex flex-col items-start gap-3">
          <Alert role="alert" className="w-full">
            {loadError}
          </Alert>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setLoading(true);
              setAttempt((n) => n + 1);
            }}
          >
            <RefreshIcon size={14} />
            Try again
          </Button>
        </div>
      ) : conversations.length === 0 ? (
        <EmptyState
          className="mt-6"
          icon={<ChatIcon size={20} />}
          title="No conversations yet"
          action={
            <Button variant="outline" size="sm" onClick={newChat} loading={creating}>
              Start your first chat
            </Button>
          }
        >
          Ask a question, rehearse an answer or paste a draft for feedback.
        </EmptyState>
      ) : (
        <ul className="stagger mt-6 flex max-w-3xl flex-col gap-2" aria-label="Your conversations">
          {conversations.map((c) => (
            <li key={c.id}>
              <ListRow
                href={`/chat/${c.id}`}
                title={c.title || "Untitled conversation"}
                meta={new Date(c.created_at).toLocaleString()}
                actions={
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => void handleDelete(c)}
                    aria-label={`Delete conversation ${c.title || "Untitled conversation"}`}
                    className="text-muted-foreground hover:bg-destructive-soft hover:text-destructive"
                  >
                    <TrashIcon size={14} />
                  </Button>
                }
              />
            </li>
          ))}
        </ul>
      )}
      {hasMore && !loading && !loadError && (
        <Button variant="outline" className="mt-4" onClick={() => void loadMore()} loading={loadingMore}>
          Show older chats
        </Button>
      )}
    </div>
  );
}
