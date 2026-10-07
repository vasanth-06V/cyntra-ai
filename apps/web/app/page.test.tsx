// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";

const state = vi.hoisted(() => ({ user: null as { id: string } | null }));
const redirect = vi.hoisted(() =>
  vi.fn((to: string) => {
    throw new Error(`REDIRECT:${to}`);
  })
);

vi.mock("next/navigation", () => ({ redirect }));
vi.mock("@/lib/supabase/server", () => ({
  createClient: async () => ({ auth: { getUser: async () => ({ data: { user: state.user } }) } }),
}));
vi.mock("next/font/google", () => {
  const font = () => ({ variable: "font-var", className: "font-class" });
  return { Bricolage_Grotesque: font, Hanken_Grotesk: font, JetBrains_Mono: font };
});
vi.mock("next-themes", () => ({ useTheme: () => ({ resolvedTheme: "light", setTheme: () => {} }) }));

import RootPage from "./page";

beforeEach(() => {
  state.user = null;
  redirect.mockClear();
});

describe("the home page", () => {
  it("shows the landing page to a visitor who is not signed in", async () => {
    render(await RootPage());
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(/Rehearse the interview/);
    expect(redirect).not.toHaveBeenCalled();
  });

  it("sends a signed-in user straight to the dashboard", async () => {
    state.user = { id: "u1" };
    await expect(RootPage()).rejects.toThrow("REDIRECT:/dashboard");
  });

  it("leads every call to action to sign-in and links the privacy page", async () => {
    render(await RootPage());
    const signIn = screen.getAllByRole("link").filter((a) => a.getAttribute("href") === "/sign-in");
    expect(signIn.length).toBeGreaterThanOrEqual(5);
    const footer = screen.getByRole("contentinfo");
    expect(within(footer).getByRole("link", { name: "Privacy" })).toHaveAttribute("href", "/privacy");
  });

  it("has the three product tabs with the first selected and the other panels hidden", async () => {
    render(await RootPage());
    const tabs = screen.getAllByRole("tab");
    expect(tabs.map((t) => t.getAttribute("aria-selected"))).toEqual(["true", "false", "false"]);
    expect(document.getElementById("panel-0")).not.toHaveAttribute("hidden");
    expect(document.getElementById("panel-1")).toHaveAttribute("hidden");
    expect(document.getElementById("panel-2")).toHaveAttribute("hidden");
  });

  it("labels the example screens as examples, never as real results", async () => {
    render(await RootPage());
    expect(screen.getAllByText(/example/i).length).toBeGreaterThan(0);
  });
});
