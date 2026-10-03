import type { ReactNode } from "react";

/** Page title block: optional eyebrow, h1, supporting line, and right-aligned actions. */
export function PageHeader({
  title,
  description,
  eyebrow,
  actions,
  className = "",
}: {
  title: ReactNode;
  description?: ReactNode;
  eyebrow?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <div className={`flex flex-wrap items-end justify-between gap-x-6 gap-y-3 ${className}`}>
      <div className="min-w-0">
        {eyebrow && (
          <p className="mb-1.5 text-xs font-medium uppercase tracking-[0.08em] text-primary">{eyebrow}</p>
        )}
        <h1 className="text-[1.65rem] font-semibold leading-tight tracking-[-0.025em] sm:text-[1.9rem]">
          {title}
        </h1>
        {description && (
          <p className="mt-1.5 max-w-2xl text-sm leading-6 text-muted-foreground">{description}</p>
        )}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}
