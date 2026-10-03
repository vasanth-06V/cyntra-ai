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

/** Main navigation links with the current page highlighted (aria-current). */
export function NavLinks({ items, variant }: { items: Item[]; variant: "side" | "bar" }) {
  const pathname = usePathname();

  return (
    <>
      {items.map((item) => {
        const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
        const Glyph = ICONS[item.href];
        const base =
          variant === "side"
            ? "group relative flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium"
            : "flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium";
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={`${base} transition-colors duration-150 ${
              active
                ? "bg-accent text-accent-foreground"
                : "text-muted-foreground hover:bg-secondary hover:text-foreground"
            }`}
          >
            {variant === "side" && (
              <span
                aria-hidden="true"
                className={`absolute -left-4 top-1/2 h-5 w-1 -translate-y-1/2 rounded-r-full bg-primary transition-opacity duration-200 ${
                  active ? "opacity-100" : "opacity-0"
                }`}
              />
            )}
            {Glyph && <Glyph size={variant === "side" ? 18 : 16} />}
            {item.label}
          </Link>
        );
      })}
    </>
  );
}
