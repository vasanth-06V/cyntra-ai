// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { scrollIntoViewSafe } from "./scroll";

function el() {
  return { scrollIntoView: vi.fn() } as unknown as Element & { scrollIntoView: ReturnType<typeof vi.fn> };
}

function setReducedMotion(reduce: boolean) {
  window.matchMedia = ((q: string) => ({
    matches: reduce && q.includes("prefers-reduced-motion"),
    media: q,
    addEventListener() {},
    removeEventListener() {},
  })) as never;
}

afterEach(() => setReducedMotion(false));

describe("scrollIntoViewSafe", () => {
  it("scrolls smoothly by default and keeps the caller's other options", () => {
    setReducedMotion(false);
    const e = el();
    scrollIntoViewSafe(e, { block: "end" });
    expect(e.scrollIntoView).toHaveBeenCalledWith({ block: "end", behavior: "smooth" });
  });

  it("jumps instead of animating when the user prefers reduced motion", () => {
    setReducedMotion(true);
    const e = el();
    scrollIntoViewSafe(e, { block: "start", behavior: "smooth" });
    expect(e.scrollIntoView).toHaveBeenCalledWith({ block: "start", behavior: "auto" });
  });

  it("does nothing for a missing element", () => {
    expect(() => scrollIntoViewSafe(null)).not.toThrow();
    expect(() => scrollIntoViewSafe(undefined)).not.toThrow();
  });
});
