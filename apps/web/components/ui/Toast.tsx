"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { AlertIcon, CheckIcon, InfoIcon, XIcon } from "./icons";

export type ToastTone = "success" | "error" | "info";

export type ToastInput = {
  title: string;
  description?: string;
  tone?: ToastTone;
  /** Milliseconds before it goes away on its own. Errors stay longer. 0 keeps it until dismissed. */
  duration?: number;
  action?: { label: string; onClick: () => void };
};

type ToastItem = ToastInput & { id: number; tone: ToastTone };

type ToastApi = {
  toast: (input: ToastInput) => number;
  dismiss: (id: number) => void;
};

const ToastContext = createContext<ToastApi | null>(null);

export function useToast(): ToastApi {
  const api = useContext(ToastContext);
  if (!api) throw new Error("useToast must be used inside <ToastProvider>");
  return api;
}

const MAX_VISIBLE = 4;

const toneStyles: Record<ToastTone, { box: string; icon: string; Glyph: typeof CheckIcon }> = {
  success: { box: "border-success/30", icon: "bg-success-soft text-success", Glyph: CheckIcon },
  error: { box: "border-destructive/30", icon: "bg-destructive-soft text-destructive", Glyph: AlertIcon },
  info: { box: "border-info/30", icon: "bg-info-soft text-info", Glyph: InfoIcon },
};

function ToastCard({ item, onDismiss }: { item: ToastItem; onDismiss: (id: number) => void }) {
  const [paused, setPaused] = useState(false);
  const { box, icon, Glyph } = toneStyles[item.tone];
  const duration = item.duration ?? (item.tone === "error" ? 8000 : 4500);

  useEffect(() => {
    if (paused || duration <= 0) return;
    const t = setTimeout(() => onDismiss(item.id), duration);
    return () => clearTimeout(t);
  }, [paused, duration, item.id, onDismiss]);

  return (
    <div
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
      className={`pointer-events-auto flex w-full animate-toast-in items-start gap-3 rounded-xl border bg-card p-3.5 text-card-foreground shadow-lg ${box}`}
    >
      <span aria-hidden="true" className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full ${icon}`}>
        <Glyph size={15} />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium leading-6">{item.title}</p>
        {item.description && <p className="text-[13px] leading-5 text-muted-foreground">{item.description}</p>}
        {item.action && (
          <button
            type="button"
            onClick={() => {
              item.action?.onClick();
              onDismiss(item.id);
            }}
            className="mt-1 cursor-pointer text-[13px] font-medium text-primary underline-offset-4 hover:underline"
          >
            {item.action.label}
          </button>
        )}
      </div>
      <button
        type="button"
        onClick={() => onDismiss(item.id)}
        aria-label="Dismiss message"
        className="-m-1 flex h-8 w-8 shrink-0 cursor-pointer items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
      >
        <XIcon size={15} />
      </button>
    </div>
  );
}

/**
 * Short-lived messages ("Resume deleted", "Could not delete"). Two persistent
 * live regions (polite for success and info, assertive for errors) exist
 * before any message arrives, so screen readers announce what appears.
 */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id: number) => {
    setItems((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback((input: ToastInput) => {
    const id = nextId.current++;
    setItems((prev) => [...prev, { ...input, id, tone: input.tone ?? "info" }].slice(-MAX_VISIBLE));
    return id;
  }, []);

  const api = useMemo(() => ({ toast, dismiss }), [toast, dismiss]);

  const polite = items.filter((t) => t.tone !== "error");
  const assertive = items.filter((t) => t.tone === "error");

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        role="region"
        aria-label="Status messages"
        className="pointer-events-none fixed inset-x-0 bottom-0 z-[60] flex flex-col items-center gap-2 p-4 sm:inset-x-auto sm:right-0 sm:w-[26rem] print:hidden"
      >
        <div aria-live="polite" className="flex w-full flex-col gap-2">
          {polite.map((t) => (
            <ToastCard key={t.id} item={t} onDismiss={dismiss} />
          ))}
        </div>
        <div aria-live="assertive" className="flex w-full flex-col gap-2">
          {assertive.map((t) => (
            <ToastCard key={t.id} item={t} onDismiss={dismiss} />
          ))}
        </div>
      </div>
    </ToastContext.Provider>
  );
}
