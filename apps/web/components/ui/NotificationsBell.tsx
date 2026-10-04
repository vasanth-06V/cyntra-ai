"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { Button } from "./Button";
import { useToast } from "./Toast";
import { BellIcon, CheckIcon, RefreshIcon } from "./icons";

type Notice = { id: string; message: string; is_read: boolean; created_at: string };

const REFRESH_MS = 60_000;

/**
 * Notices written by the backend (for example "your key stopped working" or
 * a key failover). Read straight from Supabase under the signed-in user's own
 * session: row-level security lets a user read and update only their own.
 */
export function NotificationsBell() {
  const { toast } = useToast();
  const [notices, setNotices] = useState<Notice[]>([]);
  const [loadFailed, setLoadFailed] = useState(false);
  const [open, setOpen] = useState(false);
  const wrapper = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const panelId = useId();

  const load = useCallback(async () => {
    const { data, error } = await createClient()
      .from("notifications")
      .select("id, message, is_read, created_at")
      .order("created_at", { ascending: false })
      .limit(15);
    if (error) {
      // Keep whatever is already showing; just say the refresh failed.
      setLoadFailed(true);
      return;
    }
    setLoadFailed(false);
    setNotices((data as Notice[] | null) ?? []);
  }, []);

  useEffect(() => {
    const first = setTimeout(() => void load(), 0);
    // No polling while the tab is hidden; catch up as soon as it is visible again.
    const every = setInterval(() => {
      if (!document.hidden) void load();
    }, REFRESH_MS);
    const onVisible = () => {
      if (!document.hidden) void load();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      clearTimeout(first);
      clearInterval(every);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [load]);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent && e.key === "Escape") {
        setOpen(false);
        trigger.current?.focus();
      }
      if (e instanceof MouseEvent && wrapper.current && !wrapper.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  const unread = notices.filter((n) => !n.is_read).length;

  async function markRead(ids: string[] | "all") {
    const previous = notices;
    setNotices((prev) => prev.map((n) => (ids === "all" || ids.includes(n.id) ? { ...n, is_read: true } : n)));
    const base = createClient().from("notifications").update({ is_read: true });
    const { error } = ids === "all" ? await base.eq("is_read", false) : await base.in("id", ids);
    if (error) {
      // Put the unread state back instead of pretending it worked.
      setNotices(previous);
      toast({
        tone: "error",
        title: "Could not mark as read",
        description: "Your notifications are unchanged. Please try again.",
      });
    }
  }

  return (
    <div ref={wrapper} className="relative">
      <button
        ref={trigger}
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label={unread ? `Notifications, ${unread} unread` : "Notifications"}
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        className="relative flex h-9 w-9 cursor-pointer items-center justify-center rounded-full border border-border bg-card text-muted-foreground shadow-xs transition-colors duration-150 hover:border-border-strong hover:bg-secondary hover:text-foreground"
      >
        <BellIcon size={18} />
        {unread > 0 && (
          <span
            aria-hidden="true"
            className="absolute -right-1 -top-1 min-w-[18px] rounded-full bg-destructive px-1 text-center text-[10px] font-semibold leading-[18px] text-destructive-foreground ring-2 ring-background"
          >
            {unread}
          </span>
        )}
      </button>

      {open && (
        <div
          id={panelId}
          role="region"
          aria-label="Notifications"
          className="absolute right-0 z-30 mt-2 w-[min(22rem,calc(100vw-2rem))] origin-top-right animate-pop-in rounded-xl border border-border bg-card p-3 text-card-foreground shadow-lg"
        >
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold">Notifications</h2>
            {unread > 0 && (
              <button
                type="button"
                onClick={() => void markRead("all")}
                className="cursor-pointer rounded text-xs font-medium text-primary underline-offset-4 hover:underline"
              >
                Mark all read
              </button>
            )}
          </div>

          {loadFailed && (
            <div role="alert" className="mt-2 flex items-center justify-between gap-2 rounded-lg bg-destructive-soft px-2.5 py-2 text-xs text-destructive">
              <span>Could not refresh notifications.</span>
              <Button type="button" variant="ghost" size="sm" onClick={() => void load()} className="h-7 px-2 text-xs">
                <RefreshIcon size={12} />
                Retry
              </Button>
            </div>
          )}

          {notices.length === 0 ? (
            <p className="mt-3 text-sm text-muted-foreground">
              {loadFailed ? "Nothing to show right now." : "You're all caught up."}
            </p>
          ) : (
            <ul className="mt-2 flex max-h-80 flex-col gap-1.5 overflow-y-auto">
              {notices.map((n) => (
                <li
                  key={n.id}
                  className={`rounded-lg px-2.5 py-2 text-sm leading-5 ${n.is_read ? "text-muted-foreground" : "bg-accent text-accent-foreground"}`}
                >
                  <p>{n.message}</p>
                  <div className="mt-1 flex items-center justify-between gap-2">
                    <span className="text-xs text-muted-foreground tabular-nums">
                      {new Date(n.created_at).toLocaleString()}
                    </span>
                    {!n.is_read && (
                      <button
                        type="button"
                        onClick={() => void markRead([n.id])}
                        aria-label={`Mark as read: ${n.message.slice(0, 50)}`}
                        className="inline-flex cursor-pointer items-center gap-1 rounded text-xs font-medium text-primary underline-offset-4 hover:underline"
                      >
                        <CheckIcon size={12} />
                        Mark read
                      </button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
