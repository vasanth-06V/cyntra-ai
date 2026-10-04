// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/utils";
import { serverStatus } from "@/lib/api-client/server-status";
import { ServerWakingBanner } from "./ServerWakingBanner";
import { SignOutButton } from "./SignOutButton";
import { ThemeToggle } from "./ThemeToggle";

const nav = vi.hoisted(() => ({ push: vi.fn(), refresh: vi.fn() }));
const auth = vi.hoisted(() => ({ signOut: vi.fn() }));
const theme = vi.hoisted(() => ({ resolvedTheme: "light" as string, setTheme: vi.fn() }));

vi.mock("next/navigation", () => ({ useRouter: () => nav }));
vi.mock("@/lib/supabase/client", () => ({ createClient: () => ({ auth: { signOut: auth.signOut } }) }));
vi.mock("next-themes", () => ({ useTheme: () => theme }));

beforeEach(() => {
  nav.push.mockReset();
  nav.refresh.mockReset();
  auth.signOut.mockReset();
  theme.resolvedTheme = "light";
  theme.setTheme.mockReset();
});

describe("SignOutButton", () => {
  it("signs out, then goes to the sign-in page", async () => {
    auth.signOut.mockResolvedValue({ error: null });
    renderWithProviders(<SignOutButton />);
    await userEvent.setup().click(screen.getByRole("button", { name: "Sign out" }));
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith("/sign-in"));
    expect(nav.refresh).toHaveBeenCalled();
  });

  it("is disabled and busy while signing out, and ignores a second click", async () => {
    let finish: (v: { error: null }) => void = () => {};
    auth.signOut.mockImplementation(() => new Promise((resolve) => (finish = resolve)));
    renderWithProviders(<SignOutButton />);
    const user = userEvent.setup();
    const button = screen.getByRole("button", { name: "Sign out" });
    await user.click(button);
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
    await user.click(button);
    expect(auth.signOut).toHaveBeenCalledTimes(1);
    finish({ error: null });
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith("/sign-in"));
  });

  it("stays on the page and tells the user when sign-out fails", async () => {
    auth.signOut.mockResolvedValue({ error: { message: "Network down" } });
    renderWithProviders(<SignOutButton />);
    const button = screen.getByRole("button", { name: "Sign out" });
    await userEvent.setup().click(button);
    expect(await screen.findByText("Could not sign out")).toBeInTheDocument();
    expect(screen.getByText("Network down")).toBeInTheDocument();
    expect(nav.push).not.toHaveBeenCalled();
    expect(button).toBeEnabled();
  });
});

describe("ThemeToggle", () => {
  it("offers the opposite theme and switches to it", async () => {
    // No View Transitions API in jsdom: the theme switches directly.
    render(<ThemeToggle />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Switch to dark theme" }));
    expect(theme.setTheme).toHaveBeenCalledWith("dark");
  });

  it("labels the button for the way back when the theme is dark", async () => {
    theme.resolvedTheme = "dark";
    render(<ThemeToggle />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Switch to light theme" }));
    expect(theme.setTheme).toHaveBeenCalledWith("light");
  });

  it("skips the view transition when the user prefers reduced motion", async () => {
    const start = vi.fn();
    (document as unknown as { startViewTransition: unknown }).startViewTransition = start;
    const original = window.matchMedia;
    window.matchMedia = ((q: string) => ({ matches: q.includes("reduce"), media: q, addEventListener() {}, removeEventListener() {} })) as never;
    try {
      render(<ThemeToggle />);
      await userEvent.setup().click(await screen.findByRole("button", { name: "Switch to dark theme" }));
      expect(start).not.toHaveBeenCalled();
      expect(theme.setTheme).toHaveBeenCalledWith("dark");
    } finally {
      window.matchMedia = original;
      delete (document as unknown as { startViewTransition?: unknown }).startViewTransition;
    }
  });
});

describe("ServerWakingBanner", () => {
  afterEach(() => {
    // leave the shared store idle for other tests
    act(() => {
      while (serverStatus.getSnapshot()) serverStatus.endWaking();
    });
  });

  it("is hidden normally and appears while requests are being retried", () => {
    render(<ServerWakingBanner />);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    act(() => serverStatus.beginWaking());
    expect(screen.getByRole("status")).toHaveTextContent(/waking the server/i);
    act(() => serverStatus.endWaking());
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("stays visible until every retrying request is done", () => {
    render(<ServerWakingBanner />);
    act(() => {
      serverStatus.beginWaking();
      serverStatus.beginWaking();
    });
    act(() => serverStatus.endWaking());
    expect(screen.getByRole("status")).toBeInTheDocument();
    act(() => serverStatus.endWaking());
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});
