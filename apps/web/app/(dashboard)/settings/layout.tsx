import type { ReactNode } from "react";
import { requireUser } from "@/lib/auth/guards";
import { SettingsNav } from "./SettingsNav";

export default async function SettingsLayout({ children }: { children: ReactNode }) {
  const { role } = await requireUser();
  return (
    <div className="flex flex-col gap-6 lg:flex-row lg:gap-10">
      <SettingsNav isOwner={role === "owner"} />
      <div className="min-w-0 max-w-3xl flex-1">{children}</div>
    </div>
  );
}
