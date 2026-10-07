"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ComponentType } from "react";
import { FileIcon, KeyIcon, ShieldIcon, TrashIcon, UserIcon, UsersIcon } from "@/components/ui/icons";

type Section = { href: string; label: string; icon: ComponentType<{ size?: number }>; danger?: boolean };

const SECTIONS: Section[] = [
  { href: "/settings/account", label: "Account", icon: UserIcon },
  { href: "/settings/resumes", label: "Resumes", icon: FileIcon },
  { href: "/settings/api-keys", label: "API keys", icon: KeyIcon },
  { href: "/settings/security", label: "Security", icon: ShieldIcon },
];
const TEAM: Section = { href: "/settings/team", label: "Team", icon: UsersIcon };
const DELETE: Section = { href: "/settings/delete-account", label: "Delete account", icon: TrashIcon, danger: true };

/** Section list for Settings: a side list on large screens, a scrolling row below. */
export function SettingsNav({ isOwner }: { isOwner: boolean }) {
  const pathname = usePathname();
  const sections = [...SECTIONS, ...(isOwner ? [TEAM] : []), DELETE];

  return (
    <nav aria-label="Settings sections" className="lg:w-52 lg:shrink-0">
      <h2 className="mb-2 hidden px-2.5 text-xs font-medium uppercase tracking-[0.08em] text-muted-foreground lg:block">
        Settings
      </h2>
      <ul className="-mx-3 flex gap-1 overflow-x-auto px-3 pb-1 lg:mx-0 lg:flex-col lg:overflow-visible lg:px-0 lg:pb-0">
        {sections.map(({ href, label, icon: Glyph, danger }) => {
          const active = pathname === href || pathname.startsWith(`${href}/`);
          return (
            <li key={href} className={`shrink-0 ${danger ? "lg:mt-4 lg:border-t lg:border-border lg:pt-4" : ""}`}>
              <Link
                href={href}
                aria-current={active ? "page" : undefined}
                className={`flex items-center gap-2.5 whitespace-nowrap rounded-lg px-2.5 py-2 text-sm font-medium transition-colors duration-150 ${
                  active
                    ? danger
                      ? "bg-destructive-soft text-destructive"
                      : "bg-accent text-accent-foreground"
                    : danger
                      ? "text-destructive/80 hover:bg-destructive-soft hover:text-destructive"
                      : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                }`}
              >
                <Glyph size={16} />
                {label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
