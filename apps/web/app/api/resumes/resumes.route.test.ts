import { beforeEach, describe, expect, it, vi } from "vitest";

// The route handlers talk to Supabase (row-level security) and S3-style storage;
// both are replaced here so the tests only cover the handlers' own decisions.
const state = vi.hoisted(() => ({
  user: { id: "u1" } as { id: string } | null,
  count: 0,
  existing: { file_key: "resumes/u1/a.pdf" } as { file_key: string } | null,
  deleted: [{ id: "r1" }] as { id: string }[] | null,
  deleteError: null as { message: string } | null,
  insertError: null as { message: string } | null,
  updated: [{ id: "r1", display_name: "My CV" }] as { id: string; display_name: string | null }[] | null,
  updateError: null as { message: string } | null,
  updateValues: null as Record<string, unknown> | null,
  updateFilters: [] as [string, unknown][],
}));
const upload = vi.hoisted(() => vi.fn());
const removeObject = vi.hoisted(() => vi.fn());

vi.mock("@/lib/storage", () => ({ uploadToStorage: upload, deleteFromStorage: removeObject }));
vi.mock("@/lib/supabase/server", () => ({
  createClient: async () => ({
    auth: {
      getUser: async () => ({ data: { user: state.user } }),
      getSession: async () => ({ data: { session: { access_token: "t" } } }),
    },
    from: () => ({
      select: (_cols: string, opts?: { head?: boolean }) => {
        const chain = {
          eq: () => chain,
          maybeSingle: async () => ({ data: state.existing }),
          then: (resolve: (v: unknown) => void) =>
            resolve(opts?.head ? { count: state.count, error: null } : { data: [], error: null }),
          order: async () => ({ data: [], error: null }),
        };
        return chain;
      },
      insert: () => ({
        select: () => ({
          single: async () => ({ data: state.insertError ? null : { id: "new" }, error: state.insertError }),
        }),
      }),
      update: (values: Record<string, unknown>) => {
        state.updateValues = values;
        state.updateFilters = [];
        const chain = {
          eq: (col: string, val: unknown) => {
            state.updateFilters.push([col, val]);
            return chain;
          },
          select: async () => ({
            data: state.updated && state.updated.length ? [{ id: "r1", display_name: values.display_name }] : state.updated,
            error: state.updateError,
          }),
        };
        return chain;
      },
      delete: () => {
        const chain = {
          eq: () => chain,
          select: async () => ({ data: state.deleted, error: state.deleteError }),
        };
        return chain;
      },
    }),
  }),
}));

import { POST } from "./route";
import { DELETE, PATCH } from "./[id]/route";

function uploadRequest(name = "cv.pdf", content = "%PDF-1.4 hello") {
  const form = new FormData();
  form.append("file", new File([content], name, { type: "application/pdf" }));
  return new Request("http://localhost/api/resumes", { method: "POST", body: form });
}

beforeEach(() => {
  state.user = { id: "u1" };
  state.count = 0;
  state.existing = { file_key: "resumes/u1/a.pdf" };
  state.deleted = [{ id: "r1" }];
  state.deleteError = null;
  state.insertError = null;
  state.updated = [{ id: "r1", display_name: "My CV" }];
  state.updateError = null;
  state.updateValues = null;
  state.updateFilters = [];
  upload.mockReset().mockResolvedValue("key");
  removeObject.mockReset().mockResolvedValue(undefined);
  vi.stubGlobal("fetch", vi.fn(async () => new Response("{}", { status: 200 })));
});

describe("POST /api/resumes", () => {
  it("refuses the fourth resume with a clear 409 and stores nothing", async () => {
    state.count = 3;
    const res = await POST(uploadRequest());
    expect(res.status).toBe(409);
    const body = await res.json();
    expect(body.code).toBe("resume_limit");
    expect(body.error).toMatch(/up to 3 resumes/);
    expect(upload).not.toHaveBeenCalled();
  });

  it("accepts the third resume", async () => {
    state.count = 2;
    const res = await POST(uploadRequest());
    expect(res.status).toBe(200);
    expect(upload).toHaveBeenCalledTimes(1);
  });

  it("rejects a file whose bytes are not a PDF", async () => {
    const res = await POST(uploadRequest("fake.pdf", "not a pdf"));
    expect(res.status).toBe(400);
    expect(upload).not.toHaveBeenCalled();
  });

  it("requires a signed-in user", async () => {
    state.user = null;
    expect((await POST(uploadRequest())).status).toBe(401);
  });

  it("maps the database resume_limit trigger error to the same 409 and cleans up the stored file", async () => {
    // The pre-check passed (a race, or the limit changed), but the trigger refuses the insert.
    state.insertError = { message: "resume_limit: a user may keep at most 3 resumes" };
    const res = await POST(uploadRequest());
    expect(res.status).toBe(409);
    const body = await res.json();
    expect(body.code).toBe("resume_limit");
    expect(body.error).toMatch(/up to 3 resumes/);
    expect(removeObject).toHaveBeenCalledTimes(1);
  });

  it("still reports other insert errors as 500", async () => {
    state.insertError = { message: "something else" };
    const res = await POST(uploadRequest());
    expect(res.status).toBe(500);
    expect((await res.json()).code).toBeUndefined();
  });

  it("refuses an oversized body from Content-Length alone, before reading it", async () => {
    const formData = vi.fn();
    const req = {
      headers: new Headers({ "content-length": String(5 * 1024 * 1024) }),
      formData,
    } as unknown as Request;
    const res = await POST(req);
    expect(res.status).toBe(413);
    expect((await res.json()).error).toMatch(/too large/i);
    expect(formData).not.toHaveBeenCalled();
    expect(upload).not.toHaveBeenCalled();
  });

  it("gives the processing call a timeout signal and reports success without an error", async () => {
    const res = await POST(uploadRequest());
    const body = await res.json();
    expect(body.processingError).toBeNull();
    const init = vi.mocked(fetch).mock.calls[0][1] as RequestInit;
    expect(init.signal).toBeInstanceOf(AbortSignal);
  });

  it("keeps the upload and says so when processing times out", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new DOMException("The operation timed out", "TimeoutError");
      })
    );
    const res = await POST(uploadRequest());
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.resume).toBeTruthy();
    expect(body.processingError).toMatch(/taking too long/i);
  });

  it("reports the API's own message when processing fails", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: "parse failed" }), { status: 422 })));
    const body = await (await POST(uploadRequest())).json();
    expect(body.processingError).toBe("parse failed");
  });
});

describe("PATCH /api/resumes/:id (rename)", () => {
  const call = (body: unknown, raw?: string) =>
    PATCH(
      new Request("http://localhost/api/resumes/r1", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: raw ?? JSON.stringify(body),
      }),
      { params: Promise.resolve({ id: "r1" }) }
    );

  it("trims the name, scopes the update to the owner and returns the row", async () => {
    const res = await call({ display_name: "  My CV  " });
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ id: "r1", display_name: "My CV" });
    expect(state.updateValues).toEqual({ display_name: "My CV" });
    expect(state.updateFilters).toEqual([
      ["id", "r1"],
      ["user_id", "u1"],
    ]);
  });

  it("turns an empty or blank name, and null, into null", async () => {
    for (const display_name of ["", "   ", null]) {
      state.updateValues = null;
      expect((await call({ display_name })).status).toBe(200);
      expect(state.updateValues).toEqual({ display_name: null });
    }
  });

  it("accepts exactly 80 characters and rejects 81 with a 400", async () => {
    expect((await call({ display_name: "a".repeat(80) })).status).toBe(200);
    state.updateValues = null;
    const res = await call({ display_name: "a".repeat(81) });
    expect(res.status).toBe(400);
    expect((await res.json()).error).toMatch(/80/);
    expect(state.updateValues).toBeNull();
  });

  it("rejects a non-text name and an unreadable body", async () => {
    expect((await call({ display_name: 5 })).status).toBe(400);
    expect((await call({})).status).toBe(400);
    expect((await call(null, "not json")).status).toBe(400);
  });

  it("requires a signed-in user", async () => {
    state.user = null;
    expect((await call({ display_name: "x" })).status).toBe(401);
    expect(state.updateValues).toBeNull();
  });

  it("is a 404 when no row matched (not yours, or gone)", async () => {
    state.updated = [];
    expect((await call({ display_name: "x" })).status).toBe(404);
  });

  it("reports a database error as 500", async () => {
    state.updateError = { message: "permission denied for column" };
    const res = await call({ display_name: "x" });
    expect(res.status).toBe(500);
    expect((await res.json()).error).toMatch(/permission denied/);
  });
});

describe("DELETE /api/resumes/:id", () => {
  const call = () => DELETE(new Request("http://localhost/api/resumes/r1", { method: "DELETE" }), {
    params: Promise.resolve({ id: "r1" }),
  });

  it("deletes the row and the stored file, answering 204", async () => {
    const res = await call();
    expect(res.status).toBe(204);
    expect(removeObject).toHaveBeenCalledWith("resumes/u1/a.pdf");
  });

  it("is a 404 for a resume that is not yours", async () => {
    state.existing = null;
    expect((await call()).status).toBe(404);
    expect(removeObject).not.toHaveBeenCalled();
  });

  it("reports a database error instead of pretending it worked", async () => {
    state.deleteError = { message: "violates foreign key constraint" };
    const res = await call();
    expect(res.status).toBe(500);
    expect((await res.json()).error).toMatch(/foreign key/);
    expect(removeObject).not.toHaveBeenCalled();
  });

  it("does not report success when the delete matched no rows", async () => {
    state.deleted = [];
    const res = await call();
    expect(res.status).toBe(409);
    expect(removeObject).not.toHaveBeenCalled();
  });

  it("still succeeds when the storage clean-up fails", async () => {
    removeObject.mockRejectedValue(new Error("storage down"));
    vi.spyOn(console, "error").mockImplementation(() => {});
    expect((await call()).status).toBe(204);
  });
});
