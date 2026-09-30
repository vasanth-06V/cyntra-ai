import Link from "next/link";
import type { ReactNode } from "react";
import { requireUser } from "@/lib/auth/guards";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { SignOutButton } from "@/components/ui/SignOutButton";

const NAV_ITEMS = [
  { href: "/chat", label: "Chat" },
  { href: "/interviews", label: "Interviews" },
  { href: "/ats-score", label: "ATS Score" },
  { href: "/resumes", label: "Resumes" },
  { href: "/reports", label: "Reports" },
  { href: "/settings/api-keys", label: "API Keys" },
];

export default async function DashboardLayout({
  children,
}: {
  children: ReactNode;
}) {
  const { user, role } = await requireUser();

  const navItems =
    role === "owner"
      ? [
          ...NAV_ITEMS,
          { href: "/settings/team", label: "Team" },
          { href: "/admin/question-bank", label: "Question Bank" },
        ]
      : NAV_ITEMS;

  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-56 shrink-0 flex-col border-r border-border p-4 sm:flex">
        <Link href="/dashboard" className="mb-6 px-2 text-lg font-semibold">
          CyntraAI
        </Link>
        <nav className="flex flex-col gap-1">
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
        <header className="flex items-center justify-between border-b border-border px-6 py-3">
          <span className="text-sm text-muted-foreground">{user.email}</span>
          <div className="flex items-center gap-4">
            <ThemeToggle />
            <SignOutButton />
          </div>
        </header>
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}
