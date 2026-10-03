"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createClient } from "@/lib/supabase/client";

type Notice = { id: string; message: string; is_read: boolean; created_at: string };

const REFRESH_MS = 60_000;

/**
 * Notices written by the backend (for example "your key stopped working" or
 * a key failover). Read straight from Supabase under the signed-in user's own
 * session: row-level security lets a user read and update only their own.
 */
export function NotificationsBell() {
  const [notices, setNotices] = useState<Notice[]>([]);
  const [open, setOpen] = useState(false);
  const wrapper = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    const { data } = await createClient()
      .from("notifications")
      .select("id, message, is_read, created_at")
      .order("created_at", { ascending: false })
      .limit(15);
    setNotices((data as Notice[] | null) ?? []);
  }, []);

  useEffect(() => {
    const first = setTimeout(() => void load(), 0);
    const every = setInterval(() => void load(), REFRESH_MS);
    return () => {
      clearTimeout(first);
      clearInterval(every);
    };
  }, [load]);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent && e.key === "Escape") setOpen(false);
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

  async function markAllRead() {
    setNotices((prev) => prev.map((n) => ({ ...n, is_read: true })));
    await createClient().from("notifications").update({ is_read: true }).eq("is_read", false);
  }

  return (
    <div ref={wrapper} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label={unread ? `Notifications, ${unread} unread` : "Notifications"}
        aria-expanded={open}
        className="relative cursor-pointer rounded-lg px-2 py-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <span aria-hidden="true">🔔</span>
        {unread > 0 && (
          <span
            aria-hidden="true"
            className="absolute -right-0.5 -top-0.5 min-w-4 rounded-full bg-destructive px-1 text-center text-[10px] leading-4 text-destructive-foreground"
          >
            {unread}
          </span>
        )}
      </button>

      {open && (
        <div
          role="region"
          aria-label="Notifications"
          className="absolute right-0 z-20 mt-2 w-80 rounded-xl border border-border bg-card p-3 text-card-foreground shadow-lg"
        >
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium">Notifications</h2>
            {unread > 0 && (
              <button
                type="button"
                onClick={() => void markAllRead()}
                className="cursor-pointer text-xs text-primary underline-offset-4 hover:underline"
              >
                Mark all read
              </button>
            )}
          </div>
          {notices.length === 0 ? (
            <p className="mt-3 text-sm text-muted-foreground">Nothing new.</p>
          ) : (
            <ul className="mt-2 flex max-h-72 flex-col gap-2 overflow-y-auto">
              {notices.map((n) => (
                <li
                  key={n.id}
                  className={`rounded-lg px-2 py-1.5 text-sm ${n.is_read ? "text-muted-foreground" : "bg-secondary"}`}
                >
                  {n.message}
                  <span className="mt-0.5 block text-xs text-muted-foreground">
                    {new Date(n.created_at).toLocaleString()}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
