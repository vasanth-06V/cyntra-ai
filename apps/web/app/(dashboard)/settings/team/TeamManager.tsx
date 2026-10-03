"use client";

import { useEffect, useMemo, useState } from "react";
import { apiClient, ApiError } from "@/lib/api-client/fastapi";
import { Alert } from "@/components/ui/Alert";
import { Badge, type Tone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useConfirm } from "@/components/ui/ConfirmProvider";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { ListSkeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";
import { RefreshIcon, UsersIcon } from "@/components/ui/icons";
import { initials } from "@/lib/format";
import { ROLE_LABELS, TEAM_PERMISSIONS } from "@/lib/team";
import type { TeamRole, TeamUser } from "@/types/team";

const SEARCH_THRESHOLD = 8;
const ROLE_TONE: Record<TeamRole, Tone> = { owner: "brand", admin: "info", user: "neutral" };

function displayName(u: TeamUser): string {
  return u.full_name?.trim() || u.email || "Unnamed user";
}

function Avatar({ user }: { user: TeamUser }) {
  return (
    <span
      aria-hidden="true"
      className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-accent text-sm font-semibold text-accent-foreground"
    >
      {initials(user.full_name, user.email)}
    </span>
  );
}

/**
 * Owner-only user management. Role and permission changes apply at once and
 * roll back (with an error toast) if the server refuses them.
 */
export function TeamManager({ currentUserId }: { currentUserId: string }) {
  const confirm = useConfirm();
  const { toast } = useToast();
  const [users, setUsers] = useState<TeamUser[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [query, setQuery] = useState("");
  const [pending, setPending] = useState<Set<string>>(new Set());

  useEffect(() => {
    let cancelled = false;
    apiClient
      .get<TeamUser[]>("/team/users")
      .then((list) => {
        if (cancelled) return;
        setUsers(Array.isArray(list) ? list : []);
        setError(null);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Could not load the team.");
      });
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  function setBusy(id: string, busy: boolean) {
    setPending((prev) => {
      const next = new Set(prev);
      if (busy) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  /** Swaps one user's entry; used for both the optimistic update and the rollback. */
  function replaceUser(id: string, next: TeamUser) {
    setUsers((prev) => prev?.map((u) => (u.id === id ? next : u)) ?? prev);
  }

  async function changeRole(user: TeamUser, role: "admin" | "user") {
    // Demoting to user clears permissions, so the local copy does the same.
    const optimistic: TeamUser = { ...user, role, permissions: role === "user" ? [] : user.permissions };
    replaceUser(user.id, optimistic);
    setBusy(user.id, true);
    try {
      const res = await apiClient.patch<{ id: string; role: TeamRole }>(`/team/users/${user.id}/role`, { role });
      const confirmed = res?.role ?? role;
      replaceUser(user.id, { ...optimistic, role: confirmed, permissions: confirmed === "user" ? [] : optimistic.permissions });
      toast({
        tone: "success",
        title: role === "admin" ? "Made an Admin" : "Changed to User",
        description: role === "admin" ? `${displayName(user)} can now be given permissions.` : `${displayName(user)}'s permissions were cleared.`,
      });
    } catch (err) {
      replaceUser(user.id, user);
      toast({
        tone: "error",
        title: "Could not change the role",
        description: err instanceof ApiError ? err.message : "Please try again.",
      });
    } finally {
      setBusy(user.id, false);
    }
  }

  async function demote(user: TeamUser) {
    const ok = await confirm({
      title: "Make this Admin a regular User?",
      description: (
        <>
          <span className="font-medium text-foreground">{displayName(user)}</span> will lose Admin access and every
          permission you granted.
        </>
      ),
      confirmLabel: "Make user",
      tone: "danger",
    });
    if (ok) await changeRole(user, "user");
  }

  async function togglePermission(user: TeamUser, key: string, label: string, granted: boolean) {
    const permissions = granted ? [...new Set([...user.permissions, key])] : user.permissions.filter((p) => p !== key);
    replaceUser(user.id, { ...user, permissions });
    setBusy(user.id, true);
    try {
      const res = await apiClient.put<{ id: string; permissions: string[] }>(`/team/users/${user.id}/permissions`, {
        permissions,
      });
      replaceUser(user.id, { ...user, permissions: res?.permissions ?? permissions });
      toast({
        tone: "success",
        title: granted ? "Permission granted" : "Permission removed",
        description: `${label}: ${displayName(user)}`,
      });
    } catch (err) {
      replaceUser(user.id, user);
      toast({
        tone: "error",
        title: "Could not update permissions",
        description: err instanceof ApiError ? err.message : "Please try again.",
      });
    } finally {
      setBusy(user.id, false);
    }
  }

  const visible = useMemo(() => {
    if (!users) return [];
    const q = query.trim().toLowerCase();
    if (!q) return users;
    return users.filter((u) => `${u.full_name ?? ""} ${u.email ?? ""} ${u.role}`.toLowerCase().includes(q));
  }, [users, query]);

  return (
    <div>
      <PageHeader
        title="Team"
        description="Promote users to Admin and choose what each Admin may do. Only the Owner sees this page."
      />

      {error ? (
        <div className="mt-6 flex flex-col items-start gap-3">
          <Alert role="alert" className="w-full max-w-3xl">
            {error}
          </Alert>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setError(null);
              setUsers(null);
              setAttempt((n) => n + 1);
            }}
          >
            <RefreshIcon size={14} />
            Try again
          </Button>
        </div>
      ) : users === null ? (
        <ListSkeleton className="mt-6 max-w-3xl" rows={4} label="Loading the team…" />
      ) : users.length === 0 ? (
        <EmptyState className="mt-6 max-w-3xl" icon={<UsersIcon size={20} />} title="No users yet">
          People appear here once they have signed up and finished account setup.
        </EmptyState>
      ) : (
        <>
          {users.length > SEARCH_THRESHOLD && (
            <div className="mt-6 max-w-3xl">
              <label htmlFor="team-search" className="sr-only">
                Search people
              </label>
              <input
                id="team-search"
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search by name, email or role…"
                className="field w-full"
              />
            </div>
          )}

          <p className="mt-4 text-xs text-muted-foreground" aria-live="polite">
            {visible.length} of {users.length} {users.length === 1 ? "person" : "people"}
          </p>

          {visible.length === 0 ? (
            <EmptyState className="mt-3 max-w-3xl py-8" title="No one matches that search">
              Try a different name, email or role.
            </EmptyState>
          ) : (
            <ul
              aria-label="People on your team"
              className="mt-3 flex max-w-3xl flex-col gap-3 md:gap-0 md:divide-y md:divide-border md:overflow-hidden md:rounded-xl md:border md:border-border md:bg-card md:shadow-sm"
            >
              {visible.map((u) => {
                const isSelf = u.id === currentUserId;
                const readOnly = u.role === "owner" || isSelf;
                const busy = pending.has(u.id);
                const name = displayName(u);
                return (
                  <li
                    key={u.id}
                    className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4 shadow-sm md:rounded-none md:border-0 md:shadow-none"
                  >
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
                      <div className="flex min-w-0 flex-1 basis-56 items-center gap-3">
                        <Avatar user={u} />
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium">
                            {name}
                            {isSelf && <span className="ml-1.5 text-xs font-normal text-muted-foreground">(you)</span>}
                          </p>
                          {u.full_name && u.email && (
                            <p className="truncate text-xs text-muted-foreground">{u.email}</p>
                          )}
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <Badge tone={ROLE_TONE[u.role]}>{ROLE_LABELS[u.role]}</Badge>
                        {readOnly ? (
                          <span className="text-xs text-muted-foreground">
                            {u.role === "owner" ? "Can't be changed" : "Your own role"}
                          </span>
                        ) : u.role === "user" ? (
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            disabled={busy}
                            onClick={() => void changeRole(u, "admin")}
                            aria-label={`Make ${name} an Admin`}
                          >
                            Make admin
                          </Button>
                        ) : (
                          <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            disabled={busy}
                            onClick={() => void demote(u)}
                            aria-label={`Make ${name} a User`}
                            className="text-muted-foreground hover:bg-destructive-soft hover:text-destructive"
                          >
                            Make user
                          </Button>
                        )}
                      </div>
                    </div>

                    {!readOnly && (
                      <div className="border-t border-border pt-3 md:ml-[3.25rem]">
                        {u.role === "admin" ? (
                          <fieldset className="flex flex-col gap-2" disabled={busy}>
                            <legend className="sr-only">Permissions for {name}</legend>
                            {TEAM_PERMISSIONS.map((p) => (
                              <label key={p.key} className="flex items-start gap-2.5 text-sm">
                                <input
                                  type="checkbox"
                                  checked={u.permissions.includes(p.key)}
                                  onChange={(e) => void togglePermission(u, p.key, p.label, e.target.checked)}
                                  className="mt-0.5 h-4 w-4 accent-[var(--primary)]"
                                />
                                <span>
                                  <span className="font-medium">{p.label}</span>
                                  <span className="block text-xs text-muted-foreground">{p.hint}</span>
                                </span>
                              </label>
                            ))}
                          </fieldset>
                        ) : (
                          <fieldset className="flex flex-col gap-2 opacity-60" disabled>
                            <legend className="sr-only">Permissions for {name}</legend>
                            {TEAM_PERMISSIONS.map((p) => (
                              <label key={p.key} className="flex items-center gap-2.5 text-sm">
                                <input type="checkbox" checked={false} readOnly className="h-4 w-4" />
                                <span>{p.label}</span>
                              </label>
                            ))}
                            <p className="text-xs text-muted-foreground">Make them an Admin to grant permissions.</p>
                          </fieldset>
                        )}
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
