"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { apiClient, ApiError } from "@/lib/api-client/fastapi";
import { Alert } from "@/components/ui/Alert";
import { Badge, type Tone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { LocalTime } from "@/components/ui/LocalTime";
import { PageHeader } from "@/components/ui/PageHeader";
import { useToast } from "@/components/ui/Toast";
import { initials } from "@/lib/format";
import { ROLE_LABELS } from "@/lib/team";
import type { TeamRole } from "@/types/team";

const MAX_NAME = 80;
const ROLE_TONE: Record<TeamRole, Tone> = { owner: "brand", admin: "info", user: "neutral" };

export function AccountForm({
  email,
  initialName,
  role,
  memberSince,
}: {
  email: string;
  initialName: string;
  role: TeamRole;
  memberSince: string | null;
}) {
  const router = useRouter();
  const { toast } = useToast();
  const [saved, setSaved] = useState(initialName);
  const [name, setName] = useState(initialName);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const trimmed = name.trim();
  const dirty = trimmed !== saved.trim();
  const valid = trimmed.length >= 1 && trimmed.length <= MAX_NAME;

  async function save(e: FormEvent) {
    e.preventDefault();
    if (!dirty || !valid || busy) return;
    setBusy(true);
    setError(null);
    try {
      const res = await apiClient.patch<{ full_name: string }>("/account", { full_name: trimmed });
      setSaved(res.full_name);
      setName(res.full_name);
      toast({ tone: "success", title: "Name updated" });
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save your name.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Account" description="Your profile and how you appear in CyntraAI." />

      <Card className="p-5 sm:p-6">
        <div className="flex items-center gap-4">
          <span
            aria-hidden="true"
            className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-accent text-lg font-semibold text-accent-foreground"
          >
            {initials(saved || null, email)}
          </span>
          <div className="min-w-0">
            <p className="truncate font-semibold">{saved || email}</p>
            <p className="truncate text-sm text-muted-foreground">{email}</p>
          </div>
          <Badge tone={ROLE_TONE[role]} className="ml-auto shrink-0">
            {ROLE_LABELS[role]}
          </Badge>
        </div>

        <form onSubmit={save} className="mt-6 flex flex-col gap-4" noValidate>
          <div>
            <label htmlFor="full-name" className="text-sm font-medium">
              Full name
            </label>
            <input
              id="full-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={MAX_NAME}
              autoComplete="name"
              className="field mt-1.5 w-full"
            />
          </div>
          <div>
            <label htmlFor="email" className="text-sm font-medium">
              Email
            </label>
            <input id="email" value={email} readOnly disabled className="field mt-1.5 w-full" />
            <p className="mt-1.5 text-xs text-muted-foreground">
              Your email comes from your sign-in provider and can&apos;t be changed here.
            </p>
          </div>
          {error && <Alert role="alert">{error}</Alert>}
          <div className="flex flex-wrap items-center gap-3">
            <Button type="submit" loading={busy} disabled={!dirty || !valid}>
              Save changes
            </Button>
            {memberSince && (
              <span className="text-xs text-muted-foreground">
                Member since <LocalTime iso={memberSince} dateOnly />
              </span>
            )}
          </div>
        </form>
      </Card>
    </div>
  );
}
