import { createClient } from "@/lib/supabase/client";
import { serverStatus } from "./server-status";

const API_URL = process.env.NEXT_PUBLIC_API_URL!;

/** A request that gets no answer within this long is abandoned (setup calls can be slow). */
const REQUEST_TIMEOUT_MS = 90_000;
const GET_TIMEOUT_MS = 30_000;

/**
 * Reads are retried while the server is unreachable: a free-tier host that has
 * gone to sleep needs about a minute to wake. Writes are never retried
 * automatically -- they might have reached the server.
 */
const WAKE_RETRY_DELAYS_MS = [1500, 3000, 6000, 10_000, 15_000, 20_000];
const RETRYABLE_STATUSES = new Set([502, 503, 504]);

export class ApiError extends Error {
  status: number;
  code: string;
  requestId: string | null;

  constructor(status: number, message: string, code = "error", requestId: string | null = null) {
    super(message);
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }
}

/**
 * Our API answers {error: {code, message, request_id}, detail}. Older/foreign
 * bodies may carry only `detail`, which FastAPI types as a string for our own
 * errors but as an array of {msg} objects for validation errors.
 */
function parseError(status: number, body: unknown, fallback: string, headerRequestId: string | null): ApiError {
  const b = (body ?? {}) as {
    error?: { code?: string; message?: string; request_id?: string | null };
    detail?: unknown;
  };

  let message = "";
  if (b.error?.message) message = b.error.message;
  else if (typeof b.detail === "string") message = b.detail;
  else if (Array.isArray(b.detail)) {
    message = b.detail
      .map((d) => (d && typeof d === "object" && "msg" in d ? String((d as { msg: unknown }).msg) : ""))
      .filter(Boolean)
      .join("; ");
  }

  return new ApiError(
    status,
    message || fallback || "Request failed",
    b.error?.code ?? "error",
    b.error?.request_id ?? headerRequestId
  );
}

async function errorFromResponse(res: Response): Promise<ApiError> {
  const text = await res.text().catch(() => "");
  let body: unknown = null;
  try {
    body = JSON.parse(text);
  } catch {
    body = text ? { detail: text } : null;
  }
  return parseError(res.status, body, res.statusText, res.headers.get("x-request-id"));
}

function networkError(): ApiError {
  return new ApiError(
    0,
    "Couldn't reach the server -- it may be waking up. Please try again in a moment.",
    "network_error"
  );
}

function sessionExpired(): ApiError {
  if (typeof window !== "undefined") {
    // A full navigation on purpose: it also discards any stale client state.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.assign("/sign-in");
  }
  return new ApiError(401, "Your session has expired. Please sign in again.", "unauthorized");
}

async function authHeader(): Promise<HeadersInit> {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    throw sessionExpired();
  }
  return { Authorization: `Bearer ${session.access_token}` };
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function fetchWithTimeout(url: string, init: RequestInit, timeoutMs: number): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method ?? "GET").toUpperCase();
  const isRead = method === "GET";
  const headers = {
    ...(await authHeader()),
    "Content-Type": "application/json",
    ...init?.headers,
  };
  const timeoutMs = isRead ? GET_TIMEOUT_MS : REQUEST_TIMEOUT_MS;

  let attempt = 0;
  let counted = false;
  try {
    while (true) {
      let res: Response | null = null;
      try {
        res = await fetchWithTimeout(`${API_URL}${path}`, { ...init, headers }, timeoutMs);
      } catch {
        res = null; // network failure or timeout
      }

      const unreachable = res === null || RETRYABLE_STATUSES.has(res.status);
      if (unreachable && isRead && attempt < WAKE_RETRY_DELAYS_MS.length) {
        if (!counted) {
          counted = true;
          serverStatus.beginWaking();
        }
        await sleep(WAKE_RETRY_DELAYS_MS[attempt++]);
        continue;
      }

      if (res === null) throw networkError();
      if (res.status === 401) throw sessionExpired();
      if (!res.ok) throw await errorFromResponse(res);

      if (res.status === 204) return undefined as T;
      return await res.json();
    }
  } finally {
    if (counted) serverStatus.endWaking();
  }
}

/**
 * Streams a POST response chunk-by-chunk as plain text (used for chat
 * replies). Yields each decoded chunk as it arrives, rather than waiting
 * for the full response like `apiClient.post`.
 */
async function* streamPost(path: string, body?: unknown): AsyncGenerator<string> {
  const headers = {
    ...(await authHeader()),
    "Content-Type": "application/json",
  };

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    });
  } catch {
    throw networkError();
  }

  if (res.status === 401) throw sessionExpired();
  if (!res.ok || !res.body) throw await errorFromResponse(res);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    yield decoder.decode(value, { stream: true });
  }
}

export const apiClient = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body) }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PUT", body: JSON.stringify(body) }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  streamPost,
};
