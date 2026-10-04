import { beforeEach, describe, expect, it, vi } from "vitest";

// A tiny Supabase stand-in: every table answers from `tables`, optionally with an error.
type Result = { data: unknown; error: { message: string } | null };
const db = vi.hoisted(() => ({
  user: { id: "u1" } as { id: string } | null,
  tables: {} as Record<string, Result>,
}));
const redirectMock = vi.hoisted(() =>
  vi.fn((path: string) => {
    throw new Error(`REDIRECT:${path}`);
  })
);

vi.mock("next/navigation", () => ({ redirect: redirectMock }));
vi.mock("@/lib/supabase/server", () => ({
  createClient: async () => ({
    auth: { getUser: async () => ({ data: { user: db.user } }) },
    from: (table: string) => {
      const chain: Record<string, unknown> = {};
      const result = () => db.tables[table] ?? { data: null, error: null };
      for (const m of ["select", "eq"]) chain[m] = () => chain;
      chain.maybeSingle = async () => result();
      chain.then = (resolve: (v: unknown) => void) => resolve(result());
      return chain;
    },
  }),
}));

import { GuardQueryError, requirePermission, requireRole, requireUser } from "./guards";

const ok = (data: unknown): Result => ({ data, error: null });
const failed: Result = { data: null, error: { message: "boom" } };

beforeEach(() => {
  redirectMock.mockClear();
  db.user = { id: "u1" };
  db.tables = {
    profiles: ok({ id: "u1" }),
    provider_keys: ok({ id: "k1" }),
    roles: ok({ role: "user" }),
    admin_permissions: ok([]),
  };
});

describe("requireUser", () => {
  it("returns the user, role and permissions for a fully set-up account", async () => {
    db.tables.roles = ok({ role: "admin" });
    db.tables.admin_permissions = ok([{ permission_key: "manage_question_bank" }]);
    const result = await requireUser();
    expect(result.role).toBe("admin");
    expect(result.permissions).toEqual(["manage_question_bank"]);
    expect(redirectMock).not.toHaveBeenCalled();
  });

  it("defaults to the user role when there is no role row", async () => {
    db.tables.roles = ok(null);
    expect((await requireUser()).role).toBe("user");
  });

  it("sends a signed-out visitor to sign-in", async () => {
    db.user = null;
    await expect(requireUser()).rejects.toThrow("REDIRECT:/sign-in");
  });

  it("sends a user without a profile row to account setup", async () => {
    db.tables.profiles = ok(null);
    await expect(requireUser()).rejects.toThrow("REDIRECT:/account-setup");
  });

  it("sends a user without a valid Gemini key to onboarding", async () => {
    db.tables.provider_keys = ok(null);
    await expect(requireUser()).rejects.toThrow("REDIRECT:/onboarding");
  });

  it("does NOT misroute an existing user when the profile query fails: it throws a retryable error", async () => {
    db.tables.profiles = failed;
    await expect(requireUser()).rejects.toBeInstanceOf(GuardQueryError);
    expect(redirectMock).not.toHaveBeenCalled();
  });

  it("does not send a user to onboarding when the key query fails", async () => {
    db.tables.provider_keys = failed;
    await expect(requireUser()).rejects.toBeInstanceOf(GuardQueryError);
    expect(redirectMock).not.toHaveBeenCalled();
  });

  it("throws when the role or permission query fails instead of silently downgrading", async () => {
    db.tables.roles = failed;
    await expect(requireUser()).rejects.toBeInstanceOf(GuardQueryError);
    db.tables.roles = ok({ role: "admin" });
    db.tables.admin_permissions = failed;
    await expect(requireUser()).rejects.toBeInstanceOf(GuardQueryError);
    expect(redirectMock).not.toHaveBeenCalled();
  });
});

describe("requireRole and requirePermission", () => {
  it("requireRole redirects other roles home", async () => {
    await expect(requireRole("owner")).rejects.toThrow("REDIRECT:/");
    db.tables.roles = ok({ role: "owner" });
    await expect(requireRole("owner")).resolves.toMatchObject({ role: "owner" });
  });

  it("owners always pass a permission check, admins need the permission, users never pass", async () => {
    db.tables.roles = ok({ role: "owner" });
    await expect(requirePermission("manage_question_bank")).resolves.toBeTruthy();

    db.tables.roles = ok({ role: "admin" });
    db.tables.admin_permissions = ok([]);
    await expect(requirePermission("manage_question_bank")).rejects.toThrow("REDIRECT:/");
    db.tables.admin_permissions = ok([{ permission_key: "manage_question_bank" }]);
    await expect(requirePermission("manage_question_bank")).resolves.toBeTruthy();

    db.tables.roles = ok({ role: "user" });
    await expect(requirePermission("manage_question_bank")).rejects.toThrow("REDIRECT:/");
  });
});
