import Link from "next/link";
import type { ReactNode } from "react";
import { requireUser } from "@/lib/auth/guards";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { SignOutButton } from "@/components/ui/SignOutButton";
import { NotificationsBell } from "@/components/ui/NotificationsBell";
import { ServerWakingBanner } from "@/components/ui/ServerWakingBanner";
import { NavLinks } from "@/components/ui/NavLinks";
import { Logo } from "@/components/ui/Logo";

const NAV_ITEMS = [
  { href: "/chat", label: "Chat" },
  { href: "/interviews", label: "Interviews" },
  { href: "/ats-score", label: "ATS Score" },
  { href: "/resumes", label: "Resumes" },
  { href: "/reports", label: "Reports" },
  { href: "/settings/api-keys", label: "API Keys" },
];

export async function DashboardShell({ children }: { children: ReactNode }) {
  const { user, role, permissions } = await requireUser();

  const navItems = [...NAV_ITEMS];
  if (role === "owner") {
    navItems.push({ href: "/settings/team", label: "Team" });
  }
  if (role === "owner" || permissions.includes("manage_question_bank")) {
    navItems.push({ href: "/admin/question-bank", label: "Question Bank" });
  }

  const initial = (user.email ?? "?").trim().charAt(0).toUpperCase();

  return (
    // --shell-offset: space the header, footer and page padding take, used by
    // the full-height chat and interview screens (.fill-screen).
    <div className="flex min-h-screen [--shell-offset:9.5rem] max-sm:[--shell-offset:11.75rem]">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded-lg focus:bg-primary focus:px-3 focus:py-2 focus:text-primary-foreground"
      >
        Skip to content
      </a>
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-border bg-card/70 px-4 py-5 sm:flex print:hidden">
        <Link href="/dashboard" className="mb-7 rounded-lg px-1.5" aria-label="CyntraAI dashboard">
          <Logo />
        </Link>
        <nav aria-label="Main" className="flex flex-col gap-0.5">
          <NavLinks items={navItems} variant="side" />
        </nav>
        <p className="mt-auto px-2 text-xs leading-5 text-muted-foreground">
          Practice makes calm.
          <br />
          Your keys, your data.
        </p>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-14 items-center justify-between gap-3 border-b border-border bg-background/80 px-4 backdrop-blur-md sm:px-6 print:hidden">
          <div className="flex min-w-0 items-center gap-2.5">
            <Link href="/dashboard" className="shrink-0 rounded-lg sm:hidden" aria-label="CyntraAI dashboard">
              <Logo size={26} className="[&>span:last-child]:hidden" />
            </Link>
            <span
              aria-hidden="true"
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent text-xs font-semibold text-accent-foreground"
            >
              {initial}
            </span>
            <span className="truncate text-sm text-muted-foreground">{user.email}</span>
          </div>
          <div className="flex shrink-0 items-center gap-1.5 sm:gap-2">
            <NotificationsBell />
            <ThemeToggle />
            <SignOutButton />
          </div>
        </header>
        <ServerWakingBanner />
        {/* Below sm the sidebar is hidden, so the same links run as a scrolling bar. */}
        <nav
          aria-label="Main"
          className="flex gap-1 overflow-x-auto border-b border-border bg-card/60 px-3 py-2 sm:hidden print:hidden"
        >
          <NavLinks items={navItems} variant="bar" />
        </nav>
        <main id="main" className="mx-auto w-full max-w-[84rem] flex-1 p-4 sm:p-6">
          {children}
        </main>
        <footer className="border-t border-border px-4 py-3 text-xs text-muted-foreground sm:px-6 print:hidden">
          <Link href="/privacy" className="underline-offset-4 hover:text-foreground hover:underline">
            Privacy
          </Link>
        </footer>
      </div>
    </div>
  );
}
