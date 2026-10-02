import { createClient } from "@/lib/supabase/client";

const API_URL = process.env.NEXT_PUBLIC_API_URL!;

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/**
 * FastAPI reports `detail` as a string for our own errors but as an array of
 * {loc, msg} objects for request-validation (422) errors; turn either into
 * readable text.
 */
function detailMessage(detail: unknown, fallback: string): string {
  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(detail)) {
    const msgs = detail
      .map((d) => (d && typeof d === "object" && "msg" in d ? String((d as { msg: unknown }).msg) : ""))
      .filter(Boolean);
    if (msgs.length) return msgs.join("; ");
  }
  return fallback;
}

async function authHeader(): Promise<HeadersInit> {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    throw new ApiError(401, "Not signed in");
  }
  return { Authorization: `Bearer ${session.access_token}` };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = {
    ...(await authHeader()),
    "Content-Type": "application/json",
    ...init?.headers,
  };

  const res = await fetch(`${API_URL}${path}`, { ...init, headers });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, detailMessage(body.detail, res.statusText || "Request failed"));
  }

  if (res.status === 204) {
    return undefined as T;
  }
  return res.json();
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

  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });

  if (!res.ok || !res.body) {
    const text = await res.text().catch(() => "");
    let detail: unknown = text;
    try {
      detail = JSON.parse(text).detail;
    } catch {
      // not JSON -- use the text as-is
    }
    throw new ApiError(res.status, detailMessage(detail, res.statusText || "Request failed"));
  }

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
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  streamPost,
};
