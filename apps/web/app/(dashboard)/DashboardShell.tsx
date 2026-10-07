import Link from "next/link";
import type { ReactNode } from "react";
import { requireUser } from "@/lib/auth/guards";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { SignOutButton } from "@/components/ui/SignOutButton";
import { NotificationsBell } from "@/components/ui/NotificationsBell";
import { ServerWakingBanner } from "@/components/ui/ServerWakingBanner";
import { ShellFrame } from "@/components/ui/ShellFrame";
import { SettingsIcon } from "@/components/ui/icons";

// Account-level pages (Resumes, API keys, Team...) live under Settings in the top bar.
const NAV_ITEMS = [
  { href: "/chat", label: "Chat" },
  { href: "/interviews", label: "Interviews" },
  { href: "/ats-score", label: "ATS Score" },
  { href: "/reports", label: "Reports" },
];

const iconLink =
  "flex h-9 w-9 items-center justify-center rounded-full text-muted-foreground transition-colors duration-150 hover:bg-secondary hover:text-foreground";

export async function DashboardShell({ children }: { children: ReactNode }) {
  const { user, role, permissions } = await requireUser();

  const navItems = [...NAV_ITEMS];
  if (role === "owner" || permissions.includes("manage_question_bank")) {
    navItems.push({ href: "/admin/question-bank", label: "Question Bank" });
  }

  const initial = (user.email ?? "?").trim().charAt(0).toUpperCase();

  return (
    <ShellFrame
      navItems={navItems}
      header={null}
      actions={
        <>
          <NotificationsBell />
          <ThemeToggle />
          <Link href="/settings" aria-label="Settings" title="Settings" className={iconLink}>
            <SettingsIcon size={18} />
          </Link>
          <Link
            href="/settings/account"
            aria-label={`Account: ${user.email ?? "your account"}`}
            title={user.email ?? "Account"}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent text-xs font-semibold text-accent-foreground transition-shadow duration-150 hover:ring-2 hover:ring-primary/40"
          >
            {initial}
          </Link>
          <SignOutButton />
        </>
      }
      banner={<ServerWakingBanner />}
      footer={
        <footer className="border-t border-border px-4 py-3 text-xs text-muted-foreground sm:px-6 print:hidden">
          <Link href="/privacy" className="underline-offset-4 hover:text-foreground hover:underline">
            Privacy
          </Link>
        </footer>
      }
    >
      {children}
    </ShellFrame>
  );
}
