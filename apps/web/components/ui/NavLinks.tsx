"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ComponentType } from "react";
import { BookIcon, ChatIcon, FileIcon, GaugeIcon, KeyIcon, MicIcon, ReportIcon, UsersIcon } from "./icons";

const ICONS: Record<string, ComponentType<{ size?: number }>> = {
  "/chat": ChatIcon,
  "/interviews": MicIcon,
  "/ats-score": GaugeIcon,
  "/resumes": FileIcon,
  "/reports": ReportIcon,
  "/settings/api-keys": KeyIcon,
  "/settings/team": UsersIcon,
  "/admin/question-bank": BookIcon,
};

type Item = { href: string; label: string };

/**
 * Main navigation links with the current page highlighted (aria-current).
 * `collapsed` shows icons only (the label stays available to screen readers
 * and as a tooltip).
 */
export function NavLinks({
  items,
  collapsed = false,
  onNavigate,
}: {
  items: Item[];
  collapsed?: boolean;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();

  return (
    <>
      {items.map((item) => {
        const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
        const Glyph = ICONS[item.href];
        return (
          <Link
            key={item.href}
            href={item.href}
            title={collapsed ? item.label : undefined}
            aria-label={collapsed ? item.label : undefined}
            aria-current={active ? "page" : undefined}
            onClick={onNavigate}
            className={`group relative flex items-center rounded-lg py-2 text-sm font-medium transition-colors duration-150 ${
              collapsed ? "justify-center px-2" : "gap-2.5 px-2.5"
            } ${
              active
                ? "bg-accent text-accent-foreground"
                : "text-muted-foreground hover:bg-secondary hover:text-foreground"
            }`}
          >
            <span
              aria-hidden="true"
              className={`absolute -left-3 top-1/2 h-5 w-1 -translate-y-1/2 rounded-r-full bg-primary transition-opacity duration-200 ${
                active ? "opacity-100" : "opacity-0"
              }`}
            />
            {Glyph && <Glyph size={18} />}
            {!collapsed && <span className="truncate">{item.label}</span>}
          </Link>
        );
      })}
    </>
  );
}
