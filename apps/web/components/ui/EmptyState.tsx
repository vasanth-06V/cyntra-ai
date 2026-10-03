import type { ReactNode } from "react";

/** Friendly empty/blocked state: icon, one line of what, one line of why/next. */
export function EmptyState({
  icon,
  title,
  children,
  action,
  className = "",
}: {
  icon?: ReactNode;
  title?: string;
  children?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`flex flex-col items-center gap-3 rounded-xl border border-dashed border-border-strong bg-card/60 px-6 py-10 text-center ${className}`}
    >
      {icon && (
        <span className="flex h-11 w-11 items-center justify-center rounded-full bg-accent text-accent-foreground">
          {icon}
        </span>
      )}
      {title && <p className="text-[15px] font-semibold tracking-tight">{title}</p>}
      {children && <div className="max-w-md text-sm text-muted-foreground">{children}</div>}
      {action && <div className="mt-1">{action}</div>}
    </div>
  );
}
