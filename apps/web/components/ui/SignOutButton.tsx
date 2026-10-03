"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { Spinner } from "./Spinner";
import { useToast } from "./Toast";
import { SignOutIcon } from "./icons";

export function SignOutButton() {
  const router = useRouter();
  const { toast } = useToast();
  const [busy, setBusy] = useState(false);

  async function signOut() {
    if (busy) return;
    setBusy(true);
    const { error } = await createClient().auth.signOut();
    if (error) {
      setBusy(false);
      toast({ tone: "error", title: "Could not sign out", description: error.message });
      return;
    }
    router.push("/sign-in");
    router.refresh();
  }

  return (
    <button
      type="button"
      onClick={signOut}
      disabled={busy}
      aria-busy={busy || undefined}
      className="inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-full px-3 text-sm font-medium text-muted-foreground transition-colors duration-150 hover:bg-secondary hover:text-foreground disabled:cursor-wait disabled:opacity-60"
    >
      {busy ? <Spinner size={14} /> : <SignOutIcon size={16} />}
      <span className="max-sm:sr-only">Sign out</span>
    </button>
  );
}
