"use client";

import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Alert } from "./Alert";
import { Button } from "./Button";
import { AlertIcon, InfoIcon } from "./icons";

const FOCUSABLE =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export type ConfirmDialogProps = {
  open: boolean;
  title: string;
  description?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  /** "danger" gives destructive styling and puts the first focus on Cancel. */
  tone?: "danger" | "default";
  /** The confirm action is running: the confirm button shows a spinner, nothing can dismiss the dialog. */
  busy?: boolean;
  /** A failure from the confirm action, shown inside the dialog so it cannot be missed. */
  error?: string | null;
  /** The user must type this word (any letter case) before the confirm button works. */
  requireText?: string;
  onConfirm: () => void;
  onCancel: () => void;
};

/**
 * Accessible replacement for window.confirm: role="alertdialog" with a label
 * and description, focus moves in and is trapped, Escape cancels, and the
 * opener decides where focus goes afterwards (see ConfirmProvider). Motion is
 * plain CSS, so the global reduced-motion rule covers it.
 */
export function ConfirmDialog(props: ConfirmDialogProps) {
  // The panel unmounts when closed, so what was typed never carries over to the next time.
  return props.open ? <DialogPanel {...props} /> : null;
}

function DialogPanel({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  tone = "default",
  busy = false,
  error = null,
  requireText,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const [typed, setTyped] = useState("");
  const typedId = useId();
  const panel = useRef<HTMLDivElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);
  const titleId = useId();
  const descId = useId();
  const busyRef = useRef(busy);
  const cancelFn = useRef(onCancel);
  useEffect(() => {
    busyRef.current = busy;
    cancelFn.current = onCancel;
  });

  // First focus: the safe choice for destructive actions, the action itself otherwise.
  useEffect(() => {
    if (!open) return;
    (tone === "danger" || requireText ? cancelRef.current : confirmRef.current)?.focus();
  }, [open, tone, requireText]);

  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        if (!busyRef.current) cancelFn.current();
        return;
      }
      if (e.key !== "Tab" || !panel.current) return;
      const items = Array.from(panel.current.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement;
      if (!panel.current.contains(active)) {
        e.preventDefault();
        first.focus();
      } else if (e.shiftKey && active === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [open]);

  const matches = !requireText || typed.trim().toLowerCase() === requireText.toLowerCase();
  const danger = tone === "danger";
  const Glyph = danger ? AlertIcon : InfoIcon;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-end justify-center p-4 sm:items-center">
      <div
        aria-hidden="true"
        className="absolute inset-0 animate-fade-in bg-foreground/40 backdrop-blur-[2px]"
        onClick={() => {
          if (!busy) onCancel();
        }}
      />
      <div
        ref={panel}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descId : undefined}
        className="relative w-full max-w-md animate-pop-in rounded-2xl border border-border bg-card p-6 text-card-foreground shadow-lg"
      >
        <div className="flex items-start gap-3.5">
          <span
            aria-hidden="true"
            className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${
              danger ? "bg-destructive-soft text-destructive" : "bg-accent text-accent-foreground"
            }`}
          >
            <Glyph size={20} />
          </span>
          <div className="min-w-0 flex-1">
            <h2 id={titleId} className="text-base font-semibold leading-6 tracking-tight">
              {title}
            </h2>
            {description && (
              <div id={descId} className="mt-1.5 text-sm leading-6 text-muted-foreground">
                {description}
              </div>
            )}
          </div>
        </div>

        {requireText && (
          <div className="mt-4">
            <label htmlFor={typedId} className="text-sm font-medium">
              Type <span className="font-mono font-semibold">{requireText}</span> to confirm
            </label>
            <input
              id={typedId}
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && matches && !busy) {
                  e.preventDefault();
                  onConfirm();
                }
              }}
              disabled={busy}
              autoComplete="off"
              spellCheck={false}
              className="field mt-1.5 w-full"
            />
          </div>
        )}

        {error && (
          <Alert role="alert" className="mt-4">
            {error}
          </Alert>
        )}

        <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button ref={cancelRef} type="button" variant="outline" onClick={onCancel} disabled={busy}>
            {cancelLabel}
          </Button>
          <Button
            ref={confirmRef}
            type="button"
            variant={danger ? "danger" : "primary"}
            onClick={onConfirm}
            loading={busy}
            disabled={!matches}
          >
            {error && !busy ? "Try again" : confirmLabel}
          </Button>
        </div>
      </div>
    </div>,
    document.body
  );
}
