"use client";

import { useRouter } from "next/navigation";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { useConfirm } from "@/components/ui/ConfirmProvider";
import { PageHeader } from "@/components/ui/PageHeader";
import { TrashIcon } from "@/components/ui/icons";

const GOES = [
  "Your profile and sign-in account",
  "Your resumes, including the uploaded files",
  "Your AI provider keys and usage history",
  "Your chats, interviews, coding submissions and reports",
  "Your ATS score history and notifications",
];

export function DeleteAccountForm({ isOwner }: { isOwner: boolean }) {
  const router = useRouter();
  const confirm = useConfirm();

  async function remove() {
    const ok = await confirm({
      title: "Delete your account permanently?",
      description:
        "Everything listed on this page is removed immediately and can't be restored. You'll be signed out.",
      confirmLabel: "Delete my account",
      tone: "danger",
      requireText: "continue",
      onConfirm: async () => {
        let res: Response;
        try {
          res = await fetch("/api/account", {
            method: "DELETE",
            headers: { "Content-Type": "application/json" },
            // The word the API itself requires; the user's typed confirmation is the dialog's.
            body: JSON.stringify({ confirm: "DELETE" }),
          });
        } catch {
          throw new Error("Could not reach the server. Please try again.");
        }
        if (!res.ok) {
          const body = (await res.json().catch(() => null)) as { error?: string } | null;
          throw new Error(body?.error ?? "Could not delete your account. Please try again.");
        }
      },
    });
    if (ok) {
      router.push("/sign-in");
      router.refresh();
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Delete account" description="Permanently remove your account and everything in it." />

      <section
        aria-labelledby="danger-heading"
        className="rounded-xl border border-destructive/40 bg-card p-5 shadow-sm sm:p-6"
      >
        <h2 id="danger-heading" className="text-sm font-semibold text-destructive">
          This can&apos;t be undone
        </h2>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          Deleting your account removes the following straight away. We can&apos;t restore it afterwards. Download any
          report you want to keep first.
        </p>
        <ul className="mt-3 list-disc space-y-1 pl-5 text-sm marker:text-muted-foreground">
          {GOES.map((g) => (
            <li key={g}>{g}</li>
          ))}
        </ul>

        {isOwner ? (
          <Alert tone="warning" className="mt-5">
            The Owner account can&apos;t be deleted, because the platform would be left without one.
          </Alert>
        ) : (
          <Button type="button" variant="danger" className="mt-5" onClick={() => void remove()}>
            <TrashIcon size={14} />
            Delete my account
          </Button>
        )}
      </section>
    </div>
  );
}
