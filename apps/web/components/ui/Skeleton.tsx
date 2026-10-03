import type { HTMLAttributes } from "react";

/** Decorative placeholder block; size it with className (h-*, w-*). */
export function Skeleton({ className = "", ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div aria-hidden="true" className={`skeleton ${className}`} {...props} />;
}

/**
 * A loading placeholder for a list of cards. Announces "Loading" once to
 * assistive tech; the blocks themselves are hidden from it.
 */
export function ListSkeleton({
  rows = 3,
  className = "",
  label = "Loading…",
}: {
  rows?: number;
  className?: string;
  label?: string;
}) {
  return (
    <div role="status" className={`flex flex-col gap-2 ${className}`}>
      <span className="sr-only">{label}</span>
      {Array.from({ length: rows }, (_, i) => (
        <div
          key={i}
          aria-hidden="true"
          className="flex items-center justify-between gap-4 rounded-xl border border-border bg-card p-4 shadow-sm"
        >
          <div className="flex flex-1 flex-col gap-2">
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-3 w-1/2" />
          </div>
          <Skeleton className="h-6 w-14 rounded-full" />
        </div>
      ))}
    </div>
  );
}

/** Placeholder shaped like a form card: a few fields and a button. */
export function FormSkeleton({ className = "", label = "Loading…" }: { className?: string; label?: string }) {
  return (
    <div
      role="status"
      className={`flex flex-col gap-4 rounded-xl border border-border bg-card p-5 shadow-sm ${className}`}
    >
      <span className="sr-only">{label}</span>
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-32 w-full" />
      <Skeleton className="h-10 w-32" />
    </div>
  );
}
