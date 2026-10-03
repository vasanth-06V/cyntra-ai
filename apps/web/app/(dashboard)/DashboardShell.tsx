import Link from "next/link";
import type { ReactNode } from "react";
import { requireUser } from "@/lib/auth/guards";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { SignOutButton } from "@/components/ui/SignOutButton";
import { ServerWakingBanner } from "@/components/ui/ServerWakingBanner";

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

  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-56 shrink-0 flex-col border-r border-border p-4 sm:flex print:hidden">
        <Link href="/dashboard" className="mb-6 px-2 text-lg font-semibold">
          CyntraAI
        </Link>
        <nav aria-label="Main" className="flex flex-col gap-1">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="rounded-lg px-2 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>

      <div className="flex flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-border px-6 py-3 print:hidden">
          <span className="text-sm text-muted-foreground">{user.email}</span>
          <div className="flex items-center gap-4">
            <ThemeToggle />
            <SignOutButton />
          </div>
        </header>
        <ServerWakingBanner />
        {/* Below sm the sidebar is hidden, so the same links run as a scrolling bar. */}
        <nav
          aria-label="Main"
          className="flex gap-1 overflow-x-auto border-b border-border px-4 py-2 sm:hidden print:hidden"
        >
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="shrink-0 rounded-lg px-3 py-1.5 text-sm text-muted-foreground hover:bg-secondary hover:text-foreground"
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}
