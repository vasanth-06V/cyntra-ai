// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act } from "@testing-library/react";
import { renderWithProviders } from "@/test/utils";
import { NotificationsBell } from "./NotificationsBell";

const loads = vi.hoisted(() => ({ count: 0 }));
vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    from: () => ({
      select: () => ({
        order: () => ({
          limit: async () => {
            loads.count++;
            return { data: [], error: null };
          },
        }),
      }),
    }),
  }),
}));

function setHidden(hidden: boolean) {
  Object.defineProperty(document, "hidden", { configurable: true, get: () => hidden });
}

beforeEach(() => {
  vi.useFakeTimers();
  loads.count = 0;
});
afterEach(() => {
  setHidden(false);
  vi.useRealTimers();
});

describe("NotificationsBell polling (L-23)", () => {
  it("polls every minute while the tab is visible", async () => {
    renderWithProviders(<NotificationsBell />);
    await act(async () => void vi.advanceTimersByTime(10));
    expect(loads.count).toBe(1);
    await act(async () => void vi.advanceTimersByTime(60_000));
    expect(loads.count).toBe(2);
  });

  it("does not poll while the tab is hidden, and catches up when it becomes visible", async () => {
    renderWithProviders(<NotificationsBell />);
    await act(async () => void vi.advanceTimersByTime(10));
    expect(loads.count).toBe(1);

    setHidden(true);
    await act(async () => void vi.advanceTimersByTime(5 * 60_000));
    expect(loads.count).toBe(1);

    setHidden(false);
    await act(async () => void document.dispatchEvent(new Event("visibilitychange")));
    expect(loads.count).toBe(2);
  });
});
