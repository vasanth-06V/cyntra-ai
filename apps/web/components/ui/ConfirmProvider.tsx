"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { ConfirmDialog } from "./ConfirmDialog";

export type ConfirmOptions = {
  title: string;
  description?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: "danger" | "default";
  /** The user must type this word before they can confirm (for irreversible actions). */
  requireText?: string;
  /**
   * Runs when the user confirms. The dialog stays open with a loading button
   * until it settles; if it throws, the message is shown in the dialog and
   * the user can retry or cancel.
   */
  onConfirm?: () => Promise<unknown> | unknown;
};

type Confirm = (options: ConfirmOptions) => Promise<boolean>;

const ConfirmContext = createContext<Confirm | null>(null);

/** Promise-based confirmation: `if (await confirm({ title, tone: "danger" })) ...` */
export function useConfirm(): Confirm {
  const confirm = useContext(ConfirmContext);
  if (!confirm) throw new Error("useConfirm must be used inside <ConfirmProvider>");
  return confirm;
}

type Pending = { options: ConfirmOptions; resolve: (ok: boolean) => void };

/** Focus goes back to the control that opened the dialog, or to the page content if that control is gone. */
function restoreFocus(opener: Element | null) {
  if (opener instanceof HTMLElement && opener.isConnected) {
    opener.focus();
    return;
  }
  const main = document.getElementById("main");
  if (main) {
    if (!main.hasAttribute("tabindex")) main.setAttribute("tabindex", "-1");
    main.focus({ preventScroll: true });
  }
}

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [pending, setPending] = useState<Pending | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const opener = useRef<Element | null>(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const confirm = useCallback<Confirm>((options) => {
    return new Promise<boolean>((resolve) => {
      opener.current = document.activeElement;
      setBusy(false);
      setError(null);
      setPending((current) => {
        current?.resolve(false);
        return { options, resolve };
      });
    });
  }, []);

  const finish = useCallback(
    (result: boolean) => {
      if (!pending) return;
      pending.resolve(result);
      setPending(null);
      setBusy(false);
      setError(null);
      // After the dialog has unmounted.
      setTimeout(() => restoreFocus(opener.current), 0);
    },
    [pending]
  );

  const handleConfirm = useCallback(async () => {
    if (!pending || busy) return;
    const action = pending.options.onConfirm;
    if (!action) {
      finish(true);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await action();
      if (mounted.current) finish(true);
    } catch (err) {
      if (!mounted.current) return;
      setBusy(false);
      setError(err instanceof Error && err.message ? err.message : "Something went wrong. Please try again.");
    }
  }, [pending, busy, finish]);

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      <ConfirmDialog
        open={pending !== null}
        title={pending?.options.title ?? ""}
        description={pending?.options.description}
        confirmLabel={pending?.options.confirmLabel}
        cancelLabel={pending?.options.cancelLabel}
        tone={pending?.options.tone}
        requireText={pending?.options.requireText}
        busy={busy}
        error={error}
        onConfirm={() => void handleConfirm()}
        onCancel={() => finish(false)}
      />
    </ConfirmContext.Provider>
  );
}
