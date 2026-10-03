import { afterEach, vi } from "vitest";

// Only browser-like environments need the DOM helpers; the node-only tests skip all of this.
if (typeof window !== "undefined") {
  await import("@testing-library/jest-dom/vitest");
  const { cleanup } = await import("@testing-library/react");
  const { MotionGlobalConfig } = await import("framer-motion");

  // Animations finish instantly, so exiting rows really leave the DOM in tests.
  MotionGlobalConfig.skipAnimations = true;

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    document.body.style.overflow = "";
  });

  // jsdom gaps used by the app.
  Element.prototype.scrollIntoView = vi.fn();
  window.matchMedia ??= ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
}
