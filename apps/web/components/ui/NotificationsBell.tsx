"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { BellIcon } from "./icons";

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
          role="region"
          aria-label="Notifications"
          className="absolute right-0 z-30 mt-2 w-[min(20rem,calc(100vw-2rem))] origin-top-right animate-pop-in rounded-xl border border-border bg-card p-3 text-card-foreground shadow-lg"
        >
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold">Notifications</h2>
            {unread > 0 && (
              <button
                type="button"
                onClick={() => void markAllRead()}
                className="cursor-pointer text-xs font-medium text-primary underline-offset-4 hover:underline"
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
                  className={`rounded-lg px-2.5 py-2 text-sm leading-5 ${n.is_read ? "text-muted-foreground" : "bg-accent text-accent-foreground"}`}
                >
                  {n.message}
                  <span className="mt-0.5 block text-xs text-muted-foreground tabular-nums">
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
