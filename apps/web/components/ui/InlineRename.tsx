"use client";

import { useEffect, useId, useRef, useState } from "react";
import { Button } from "./Button";
import { CheckIcon, XIcon } from "./icons";

/**
 * An inline text editor for renaming something in place.
 *
 * Enter saves, Escape cancels, focus lands in the field on open. `validate`
 * runs on every change and blocks saving; `onSave` may throw an Error whose
 * message is shown under the field (the editor stays open so the user can
 * retry). The parent owns "is editing" and closes the editor via `onClose`.
 */
export function InlineRename({
  initialValue,
  label,
  placeholder,
  maxLength,
  validate,
  onSave,
  onClose,
  className = "",
}: {
  initialValue: string;
  /** Accessible name of the input, for example "New name for cv.pdf". */
  label: string;
  placeholder?: string;
  maxLength?: number;
  /** Returns a message when the current value cannot be saved, otherwise null. */
  validate?: (value: string) => string | null;
  /** Saves the value; throw to keep the editor open with the message. */
  onSave: (value: string) => Promise<void>;
  /** Called after a successful save or when the user cancels. */
  onClose: (saved: boolean) => void;
  className?: string;
}) {
  const [value, setValue] = useState(initialValue);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const errorId = useId();
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    inputRef.current?.focus();
    inputRef.current?.select();
    return () => {
      mounted.current = false;
    };
  }, []);

  const problem = validate?.(value) ?? null;
  const shown = problem ?? error;

  async function save() {
    if (saving || problem) return;
    if (value.trim() === initialValue.trim()) {
      onClose(false);
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await onSave(value);
      onClose(true);
    } catch (err) {
      if (mounted.current) {
        setError(err instanceof Error ? err.message : "Could not save the new name.");
        setSaving(false);
        inputRef.current?.focus();
      }
    }
  }

  return (
    <div className={`flex min-w-0 flex-col gap-1.5 ${className}`}>
      <div className="flex min-w-0 flex-wrap items-center gap-2">
        <input
          ref={inputRef}
          type="text"
          value={value}
          aria-label={label}
          aria-invalid={shown ? true : undefined}
          aria-describedby={shown ? errorId : undefined}
          placeholder={placeholder}
          // Allow typing past the limit so the message can explain, instead of silently truncating.
          maxLength={maxLength ? maxLength + 20 : undefined}
          disabled={saving}
          onChange={(e) => {
            setValue(e.target.value);
            setError(null);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              e.stopPropagation();
              void save();
            } else if (e.key === "Escape") {
              e.preventDefault();
              e.stopPropagation();
              onClose(false);
            }
          }}
          className="field field-sm min-w-0 flex-1"
        />
        <Button
          type="button"
          size="sm"
          onClick={() => void save()}
          loading={saving}
          disabled={!!problem}
          aria-label="Save name"
        >
          {!saving && <CheckIcon size={14} />}
          Save
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={() => onClose(false)} disabled={saving} aria-label="Cancel rename">
          <XIcon size={14} />
          Cancel
        </Button>
      </div>
      {shown && (
        <p id={errorId} role="alert" className="text-xs text-destructive">
          {shown}
        </p>
      )}
    </div>
  );
}
