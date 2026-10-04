// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const session = vi.hoisted(() => ({ value: { access_token: "tok" } as { access_token: string } | null }));
vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({ auth: { getSession: async () => ({ data: { session: session.value } }) } }),
}));

import { ApiError, apiClient } from "./fastapi";
import { serverStatus } from "./server-status";

const json = (body: unknown, status = 200, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", ...headers } });

const assign = vi.fn();

beforeEach(() => {
  vi.useFakeTimers();
  session.value = { access_token: "tok" };
  assign.mockReset();
  vi.stubGlobal("location", { assign });
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

/** Runs a call to the end while letting the retry back-off timers fire. */
async function settle<T>(promise: Promise<T>): Promise<PromiseSettledResult<T>> {
  const result = promise.then(
    (value) => ({ status: "fulfilled", value }) as const,
    (reason) => ({ status: "rejected", reason }) as const
  );
  await vi.advanceTimersByTimeAsync(120_000);
  return result;
}

describe("apiClient requests", () => {
  it("sends the bearer token and parses JSON", async () => {
    const fetchMock = vi.fn(async () => json([{ id: 1 }]));
    vi.stubGlobal("fetch", fetchMock);
    const res = await settle(apiClient.get<{ id: number }[]>("/keys"));
    expect(res).toMatchObject({ status: "fulfilled", value: [{ id: 1 }] });
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url.endsWith("/keys")).toBe(true);
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer tok");
  });

  it("sends JSON bodies for POST and returns undefined for 204", async () => {
    const fetchMock = vi.fn(async () => new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    const res = await settle(apiClient.post("/x", { a: 1 }));
    expect(res).toMatchObject({ status: "fulfilled", value: undefined });
    const init = (fetchMock.mock.calls[0] as unknown as [string, RequestInit])[1];
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ a: 1 }));
  });

  it("redirects to sign-in without calling the API when there is no session", async () => {
    session.value = null;
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const res = await settle(apiClient.get("/keys"));
    expect(res).toMatchObject({ status: "rejected" });
    expect(fetchMock).not.toHaveBeenCalled();
    expect(assign).toHaveBeenCalledWith("/sign-in");
  });

  it("redirects to sign-in on a 401 and throws a readable error", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json({ detail: "expired" }, 401)));
    const res = await settle(apiClient.get("/keys"));
    expect(res.status).toBe("rejected");
    const err = (res as PromiseRejectedResult).reason as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(401);
    expect(err.code).toBe("unauthorized");
    expect(assign).toHaveBeenCalledWith("/sign-in");
  });
});

describe("apiClient retries", () => {
  it("retries a GET on 503 and then succeeds, showing the waking banner meanwhile", async () => {
    const seen: boolean[] = [];
    const unsubscribe = serverStatus.subscribe(() => seen.push(serverStatus.getSnapshot()));
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(json({}, 503))
      .mockResolvedValueOnce(json({}, 502))
      .mockResolvedValueOnce(json({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    const res = await settle(apiClient.get("/keys"));
    unsubscribe();
    expect(res).toMatchObject({ status: "fulfilled", value: { ok: true } });
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(seen).toEqual([true, false]);
    expect(serverStatus.getSnapshot()).toBe(false);
  });

  it("retries a GET after a network error", async () => {
    const fetchMock = vi.fn().mockRejectedValueOnce(new TypeError("Failed to fetch")).mockResolvedValueOnce(json([]));
    vi.stubGlobal("fetch", fetchMock);
    const res = await settle(apiClient.get("/keys"));
    expect(res).toMatchObject({ status: "fulfilled", value: [] });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("gives up after the back-off schedule and reports a network error", async () => {
    const fetchMock = vi.fn(async () => json({}, 503));
    vi.stubGlobal("fetch", fetchMock);
    const res = await settle(apiClient.get("/keys"));
    expect(res.status).toBe("rejected");
    // 1 first try + 6 retries; the last 503 is then an error response.
    expect(fetchMock).toHaveBeenCalledTimes(7);
    expect((res as PromiseRejectedResult).reason).toBeInstanceOf(ApiError);
    expect(serverStatus.getSnapshot()).toBe(false);
  });

  it("never retries a POST, even on 503 or a network failure", async () => {
    const fetchMock = vi.fn(async () => json({ detail: "busy" }, 503));
    vi.stubGlobal("fetch", fetchMock);
    const res = await settle(apiClient.post("/interviews", {}));
    expect(res.status).toBe("rejected");
    expect(fetchMock).toHaveBeenCalledTimes(1);

    const failing = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    vi.stubGlobal("fetch", failing);
    const res2 = await settle(apiClient.post("/interviews", {}));
    expect(res2.status).toBe("rejected");
    expect(((res2 as PromiseRejectedResult).reason as ApiError).code).toBe("network_error");
    expect(failing).toHaveBeenCalledTimes(1);
  });

  it("does not retry a plain error status such as 404 or 500", async () => {
    const fetchMock = vi.fn(async () => json({ detail: "nope" }, 404));
    vi.stubGlobal("fetch", fetchMock);
    const res = await settle(apiClient.get("/missing"));
    expect(res.status).toBe("rejected");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("keeps the banner up until the last of two concurrent retrying reads finishes", async () => {
    let releaseSecond: () => void = () => {};
    const fetchMock = vi.fn(async (url: string) => {
      if (url.endsWith("/a")) {
        return fetchMock.mock.calls.filter((c) => (c[0] as string).endsWith("/a")).length === 1 ? json({}, 503) : json([]);
      }
      if (fetchMock.mock.calls.filter((c) => (c[0] as string).endsWith("/b")).length === 1) return json({}, 503);
      await new Promise<void>((resolve) => (releaseSecond = resolve));
      return json([]);
    });
    vi.stubGlobal("fetch", fetchMock);
    const a = apiClient.get("/a");
    const b = apiClient.get("/b");
    await vi.advanceTimersByTimeAsync(2000);
    await a;
    expect(serverStatus.getSnapshot()).toBe(true); // /b is still retrying
    releaseSecond();
    await vi.advanceTimersByTimeAsync(10);
    await b;
    expect(serverStatus.getSnapshot()).toBe(false);
  });
});

describe("apiClient error envelope", () => {
  const rejection = async (response: Response) => {
    vi.stubGlobal("fetch", vi.fn(async () => response));
    const res = await settle(apiClient.post("/x", {}));
    expect(res.status).toBe("rejected");
    return (res as PromiseRejectedResult).reason as ApiError;
  };

  it("reads code, message and request id from the error envelope", async () => {
    const err = await rejection(
      json({ error: { code: "interview_ended", message: "Time is up", request_id: "r-1" }, detail: "x" }, 409)
    );
    expect(err).toMatchObject({ status: 409, code: "interview_ended", message: "Time is up", requestId: "r-1" });
  });

  it("falls back to a string detail and to the x-request-id header", async () => {
    const err = await rejection(json({ detail: "Not allowed" }, 403, { "x-request-id": "hdr-9" }));
    expect(err).toMatchObject({ status: 403, message: "Not allowed", code: "error", requestId: "hdr-9" });
  });

  it("joins validation errors from a detail array", async () => {
    const err = await rejection(json({ detail: [{ msg: "too short" }, { msg: "bad value" }, { loc: ["x"] }] }, 422));
    expect(err.message).toBe("too short; bad value");
  });

  it("copes with a non-JSON body (an HTML error page)", async () => {
    const err = await rejection(new Response("<html>Bad gateway</html>", { status: 500, statusText: "Server Error" }));
    expect(err.status).toBe(500);
    expect(err.message).toContain("Bad gateway");
  });

  it("copes with an empty body and uses the status text", async () => {
    const err = await rejection(new Response(null, { status: 500, statusText: "Internal Server Error" }));
    expect(err.message).toBe("Internal Server Error");
  });
});

describe("apiClient.streamPost", () => {
  it("yields decoded chunks as they arrive", async () => {
    const encoder = new TextEncoder();
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode("Hel"));
        controller.enqueue(encoder.encode("lo"));
        controller.close();
      },
    });
    vi.stubGlobal("fetch", vi.fn(async () => new Response(body, { status: 200 })));
    const chunks: string[] = [];
    for await (const c of apiClient.streamPost("/chat", { content: "hi" })) chunks.push(c);
    expect(chunks.join("")).toBe("Hello");
  });

  it("throws the API's error for a non-OK response and a network error when unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json({ error: { code: "rate_limited", message: "Slow down" } }, 429)));
    await expect((async () => { for await (const _ of apiClient.streamPost("/chat", {})) void _; })()).rejects.toMatchObject({
      status: 429,
      code: "rate_limited",
    });
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("down")));
    await expect((async () => { for await (const _ of apiClient.streamPost("/chat", {})) void _; })()).rejects.toMatchObject({
      code: "network_error",
    });
  });
});
