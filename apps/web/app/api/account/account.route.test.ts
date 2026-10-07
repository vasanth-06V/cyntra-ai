import { beforeEach, describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({
  user: { id: "u1" } as { id: string } | null,
  keys: [{ file_key: "resumes/u1/a.pdf" }, { file_key: "resumes/u1/b.pdf" }] as { file_key: string }[],
  keysError: null as { message: string } | null,
}));
const removeObject = vi.hoisted(() => vi.fn());
const signOut = vi.hoisted(() => vi.fn());

vi.mock("@/lib/storage", () => ({ deleteFromStorage: removeObject }));
vi.mock("@/lib/supabase/server", () => ({
  createClient: async () => ({
    auth: {
      getUser: async () => ({ data: { user: state.user } }),
      getSession: async () => ({ data: { session: { access_token: "t" } } }),
      signOut,
    },
    from: () => ({
      select: () => ({ eq: async () => ({ data: state.keys, error: state.keysError }) }),
    }),
  }),
}));

import { DELETE } from "./route";

const request = (body: unknown) =>
  new Request("http://localhost/api/account", { method: "DELETE", body: JSON.stringify(body) });

const fetchMock = vi.fn();

beforeEach(() => {
  state.user = { id: "u1" };
  state.keysError = null;
  removeObject.mockReset().mockResolvedValue(undefined);
  signOut.mockReset().mockResolvedValue({});
  fetchMock.mockReset().mockResolvedValue(new Response(null, { status: 204 }));
  vi.stubGlobal("fetch", fetchMock);
});

describe("DELETE /api/account", () => {
  it("needs a signed-in user", async () => {
    state.user = null;
    expect((await DELETE(request({ confirm: "DELETE" }))).status).toBe(401);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("needs the typed confirmation and does nothing without it", async () => {
    expect((await DELETE(request({ confirm: "delete" }))).status).toBe(400);
    expect((await DELETE(request({}))).status).toBe(400);
    expect(fetchMock).not.toHaveBeenCalled();
    expect(removeObject).not.toHaveBeenCalled();
  });

  it("deletes the account through the API, then the resume files, then signs out", async () => {
    const res = await DELETE(request({ confirm: "DELETE" }));
    expect(res.status).toBe(204);
    expect(fetchMock).toHaveBeenCalledOnce();
    expect(String(fetchMock.mock.calls[0][0])).toMatch(/\/account\/delete$/);
    expect(removeObject.mock.calls.map((c) => c[0]).sort()).toEqual(["resumes/u1/a.pdf", "resumes/u1/b.pdf"]);
    expect(signOut).toHaveBeenCalled();
  });

  it("keeps every file when the API refuses (the Owner account)", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ error: { code: "owner_cannot_delete", message: "The Owner account can't be deleted." } }), {
        status: 409,
      })
    );
    const res = await DELETE(request({ confirm: "DELETE" }));
    expect(res.status).toBe(409);
    expect((await res.json()).error).toMatch(/Owner/);
    expect(removeObject).not.toHaveBeenCalled();
    expect(signOut).not.toHaveBeenCalled();
  });

  it("still succeeds when a file can't be removed from storage", async () => {
    removeObject.mockRejectedValueOnce(new Error("storage down"));
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    expect((await DELETE(request({ confirm: "DELETE" }))).status).toBe(204);
  });

  it("reports an unreachable API without touching files", async () => {
    fetchMock.mockRejectedValue(new TypeError("fetch failed"));
    expect((await DELETE(request({ confirm: "DELETE" }))).status).toBe(502);
    expect(removeObject).not.toHaveBeenCalled();
  });
});
