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
import { DELETE } from "./[id]/route";

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
