import { vi } from "vitest";
import type { ReactElement } from "react";
import { render } from "@testing-library/react";
import { ConfirmProvider } from "@/components/ui/ConfirmProvider";
import { ToastProvider } from "@/components/ui/Toast";

/** Renders with the same app-wide providers as app/layout.tsx (toasts and confirm dialogs). */
export function renderWithProviders(ui: ReactElement) {
  return render(
    <ToastProvider>
      <ConfirmProvider>{ui}</ConfirmProvider>
    </ToastProvider>
  );
}

type Route = { method?: string; match: string | RegExp; status?: number; json?: unknown; onCall?: () => void; body?: BodyInit | null; delayMs?: number };

/**
 * A fetch mock driven by a route table: the first matching route answers.
 * Unmatched calls fail loudly so a test never silently hits the network.
 */
export function mockFetch(routes: Route[]) {
  const calls: { url: string; method: string; body?: BodyInit | null }[] = [];
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    const method = (init?.method ?? "GET").toUpperCase();
    calls.push({ url, method, body: init?.body });
    const route = routes.find(
      (r) =>
        (r.method ?? "GET").toUpperCase() === method &&
        (typeof r.match === "string" ? url === r.match : r.match.test(url))
    );
    if (!route) throw new Error(`Unmocked fetch: ${method} ${url}`);
    if (route.delayMs) await new Promise((r) => setTimeout(r, route.delayMs));
    route.onCall?.();
    const status = route.status ?? 200;
    return new Response(status === 204 ? null : JSON.stringify(typeof route.json === "function" ? (route.json as () => unknown)() : (route.json ?? {})), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  });
  vi.stubGlobal("fetch", fn);
  return { fn, calls };
}
