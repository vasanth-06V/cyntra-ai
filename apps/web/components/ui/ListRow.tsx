import Link from "next/link";
import type { ReactNode } from "react";
import { ChevronRightIcon } from "./icons";

/**
 * One row in a list of things (resumes, chats, interviews, reports).
 *
 * With `href`, the title is the link and its hit area stretches over the whole
 * row (a "stretched link"), while `actions` sit above it, so a row can be both
 * clickable and carry its own buttons without nesting interactive elements.
 */
export function ListRow({
  icon,
  leading,
  title,
  meta,
  badge,
  trailing,
  href,
  actions,
  className = "",
}: {
  icon?: ReactNode;
  /** A custom leading element (for example a score ring), shown without the icon tile. */
  leading?: ReactNode;
  title: ReactNode;
  meta?: ReactNode;
  badge?: ReactNode;
  /** Right-aligned summary, for example a score. */
  trailing?: ReactNode;
  href?: string;
  actions?: ReactNode;
  className?: string;
}) {
  const heading = href ? (
    <Link
      href={href}
      className="block truncate rounded text-sm font-medium after:absolute after:inset-0 after:rounded-xl after:content-['']"
    >
      {title}
    </Link>
  ) : (
    <p className="truncate text-sm font-medium">{title}</p>
  );

  return (
    <div
      className={`group relative flex flex-wrap items-center justify-between gap-x-4 gap-y-3 rounded-xl border border-border bg-card p-4 text-card-foreground shadow-sm transition-[transform,box-shadow,border-color] duration-200 ease-out has-[a:focus-visible]:ring-2 has-[a:focus-visible]:ring-ring ${
        href
          ? "hover:-translate-y-0.5 hover:border-border-strong hover:shadow-md motion-reduce:hover:translate-y-0"
          : ""
      } ${className}`}
    >
      <div className="flex min-w-0 flex-1 items-center gap-3.5">
        {leading}
        {icon && (
          <span
            aria-hidden="true"
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent text-accent-foreground"
          >
            {icon}
          </span>
        )}
        <div className="min-w-0 flex-1">
          {heading}
          {meta && <p className="mt-0.5 text-xs text-muted-foreground tabular-nums">{meta}</p>}
          {badge && <div className="mt-1.5 flex flex-wrap items-center gap-1.5">{badge}</div>}
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {trailing}
        {actions && <div className="relative z-10 flex items-center gap-1.5">{actions}</div>}
        {href && !actions && (
          <ChevronRightIcon
            size={18}
            className="text-muted-foreground transition-transform duration-200 group-hover:translate-x-0.5 group-hover:text-primary motion-reduce:transform-none"
          />
        )}
      </div>
    </div>
  );
}
